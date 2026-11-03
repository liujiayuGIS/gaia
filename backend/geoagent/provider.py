"""Responses and Chat Completions adapters with redacted provider diagnostics."""
from __future__ import annotations
import os
import re
from urllib.parse import urlparse
import httpx

DEFAULT_OUTPUT_TOKENS=8192


def output_budget(config):
    value=config.get('max_output_tokens',DEFAULT_OUTPUT_TOKENS)
    if isinstance(value,bool) or not isinstance(value,int) or not 256<=value<=32768:
        raise ValueError('模型输出预算应为 256–32768 tokens，并须在服务商支持范围内。')
    return value


def resolve_config(base_url, model, api_key, protocol="auto", reasoning_effort="medium", max_output_tokens=DEFAULT_OUTPUT_TOKENS):
    base=(base_url or os.environ.get('GIS_LLM_BASE_URL','https://api.deepseek.com')).strip().rstrip('/')
    parsed=urlparse(base)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('模型地址必须是无凭据、查询参数和片段的 HTTP(S) API 根地址。')
    if parsed.path.endswith(('/chat/completions','/responses','/models')):
        raise ValueError('请填写 API 根地址，不要包含 /chat/completions、/responses 或 /models。')
    if parsed.hostname=='api.openai.com' and parsed.path.rstrip('/')!='/v1':
        raise ValueError('OpenAI 官方 API 根地址请填写 https://api.openai.com/v1。')
    name=model.strip()
    if not name:
        raise ValueError('请填写具体模型名称。')
    key=api_key.strip() or os.environ.get('GIS_LLM_API_KEY','').strip()
    if not key:
        raise ValueError('请配置 API Key，或切换到离线指令模式。')
    if protocol not in ('auto','responses','chat_completions') or reasoning_effort not in ('none','low','medium','high'):
        raise ValueError('接口协议或推理强度无效。')
    selected=('responses' if parsed.hostname=='api.openai.com' else 'chat_completions') if protocol=='auto' else protocol
    config={'base_url':base,'model':name,'api_key':key,'protocol':selected,'reasoning_effort':reasoning_effort,
            'max_output_tokens':max_output_tokens}
    output_budget(config)
    return config


def completion_payload(config, messages, tools):
    model=config['model']
    openai_reasoning=bool(re.match(r'^(?:gpt-[5-9](?:[.\-]|$)|o[1-9](?:[.\-]|$))',model))
    reasoning_model=openai_reasoning or model.startswith('deepseek-reasoner')
    official=urlparse(config['base_url']).hostname=='api.openai.com'
    payload={'model':model,'messages':messages,'tools':tools}
    if official or openai_reasoning:
        payload['max_completion_tokens']=output_budget(config)
    else:
        payload['max_tokens']=output_budget(config)
    # Leave sampling at the provider's defaults for reasoning models.
    if not reasoning_model:
        payload['temperature']=0.1
    # GPT-5.6 Sol (including its alias/snapshots) requires non-reasoning
    # mode when function tools are declared on Chat Completions.
    # Scope this rule narrowly: other reasoning models may reject "none".
    if tools and re.fullmatch(r'gpt-5\.6(?:-sol)?(?:-\d{4}-\d{2}-\d{2})?',model):
        payload['reasoning_effort']='none'
    return payload


def redact(value, secret=''):
    text=str(value)
    if secret:
        text=text.replace(secret,'[密钥已隐藏]')
    text=re.sub(r'\bsk-[A-Za-z0-9_-]+','[密钥已隐藏]',text)
    text=re.sub(r'(?i)Bearer\s+[^\s\"\'<>]+','Bearer [密钥已隐藏]',text)
    return text[:700]


class ProviderError(ValueError):
    def __init__(self, details):
        self.details=details
        super().__init__(details['message'])


def error_details(response, secret=''):
    code=param=provider_message=''
    try:
        body=response.json()
        error=body.get('error',{}) if isinstance(body,dict) else {}
        if isinstance(error,dict):
            code=redact(error.get('code') or error.get('type') or '',secret)
            param=redact(error.get('param') or '',secret)
            provider_message=redact(error.get('message') or '',secret)
        elif isinstance(error,str):
            provider_message=redact(error,secret)
    except (ValueError,TypeError):
        pass
    status=response.status_code
    hint={
        400:'请求参数被拒绝；请查看下方具体参数说明。',
        401:'密钥无效或已失效，请检查当前服务商的 API Key。',
        403:'当前密钥、项目或地区没有此请求的访问权限。',
        404:'请求的模型或接口不存在，或当前项目没有访问该模型的权限。',
        429:'请求限流或 API 额度不足；请查看服务商错误码。',
    }.get(status,'模型服务暂时不可用，请稍后重试。' if status>=500 else '模型服务拒绝了请求。')
    lines=[f'模型服务返回 HTTP {status}。{hint}']
    if code:
        lines.append('错误码：'+code)
    if param:
        lines.append('参数：'+param)
    if provider_message:
        lines.append('服务说明：'+provider_message)
    elif not code:
        lines.append('服务未返回标准 JSON 错误详情，请检查 API 根地址和网络代理。')
    return {'status':status,'code':code,'param':param,'message':'\n'.join(lines)}


def request_completion(client, config, payload):
    try:
        response=client.post(config['base_url'].rstrip('/')+'/chat/completions',
                             headers={'Authorization':'Bearer '+config['api_key']},json=payload)
    except httpx.TimeoutException:
        raise ProviderError({'status':None,'code':'timeout','message':'模型请求超时。请检查网络连接，或稍后重试。'}) from None
    except httpx.RequestError:
        raise ProviderError({'status':None,'code':'connection_error','message':'无法连接模型服务。请检查 API 根地址、网络与代理设置。'}) from None
    if not response.is_success:
        raise ProviderError(error_details(response,config['api_key']))
    try:
        data=response.json()
        message=data['choices'][0]['message']
        if not isinstance(message,dict) or message.get('role')!='assistant':
            raise ValueError('invalid assistant message')
    except (ValueError,KeyError,IndexError,TypeError):
        raise ProviderError({'status':response.status_code,'code':'invalid_response','message':'模型服务返回了不符合 Chat Completions 格式的响应，请确认接口协议。'}) from None
    return data


def test_connection(config, tools):
    with httpx.Client(timeout=httpx.Timeout(90,connect=10),follow_redirects=False) as client:
        if config.get('protocol')=='responses':
            payload=responses_payload(config,[{'role':'user','content':'请只回复 OK。'}],tools,'你是连接测试助手。只回复 OK，不调用工具。')
            payload['tool_choice']='none'
            data=request_responses(client,config,payload)
            note='Responses API；保留推理与工具调用能力。'
        else:
            payload=completion_payload(config,[{'role':'user','content':'请只回复 OK。'}],tools)
            payload['tool_choice']='none'
            data=request_completion(client,config,payload)
            note='Chat Completions；'+('当前模型工具调用使用非推理兼容模式。' if payload.get('reasoning_effort')=='none' else '')
    return {'ok':True,'model':data.get('model',config['model']),'protocol':config.get('protocol','chat_completions'),
            'message':'连接成功。'+note+'此测试未读取地理数据，也未运行 GIS 工具。'}


def responses_payload(config,inputs,tools,instructions):
    flattened=[]
    for tool in tools:
        fn=tool['function']
        flattened.append({'type':'function','name':fn['name'],'description':fn.get('description',''),
                          'parameters':fn['parameters'],'strict':False})
    return {'model':config['model'],'instructions':instructions,'input':inputs,'tools':flattened,
            'reasoning':{'effort':config.get('reasoning_effort','medium')},'max_output_tokens':output_budget(config),
            'store':False,'include':['reasoning.encrypted_content']}


def request_responses(client,config,payload):
    try:
        response=client.post(config['base_url'].rstrip('/')+'/responses',headers={'Authorization':'Bearer '+config['api_key']},json=payload)
    except httpx.TimeoutException:
        raise ProviderError({'status':None,'code':'timeout','message':'模型请求超时。推理任务可能需要更长时间，请降低推理强度或稍后重试。'}) from None
    except httpx.RequestError:
        raise ProviderError({'status':None,'code':'connection_error','message':'无法连接模型 Responses 接口，请检查网络和地址。'}) from None
    if not response.is_success:
        raise ProviderError(error_details(response,config['api_key']))
    try:
        data=response.json()
        if not isinstance(data.get('output'),list):raise ValueError()
    except (ValueError,TypeError,AttributeError):
        raise ProviderError({'status':200,'code':'invalid_response','message':'服务响应不符合 Responses API，请检查接口协议。'}) from None
    if data.get('status') in ('failed','incomplete','cancelled'):
        reason=(data.get('incomplete_details') or data.get('error') or {}).get('reason','未完成')
        if reason=='max_output_tokens':
            raise output_limit_error(config,data.get('usage',{}),'max_output_tokens')
        raise ProviderError({'status':200,'code':'incomplete','message':'模型未完成本轮响应：'+redact(reason,config['api_key'])})
    return data


def response_text(data):
    return '\n'.join(part.get('text','') for item in data['output'] if item.get('type')=='message' for part in item.get('content',[]) if part.get('type')=='output_text')


def output_limit_error(config,usage=None,param='max_completion_tokens'):
    budget=output_budget(config)
    return ProviderError({'status':200,'code':'output_limit','param':param,'max_output_tokens':budget,
        'usage':usage or {},'message':f'模型本轮输出达到 {budget} tokens 上限（可能包含推理）。'
        '本轮不完整的工具调用未执行，已有成果和检查点保留。请在模型设置中提高“每轮输出预算”，再从检查点继续；服务商也可能有更低的上限。'})
