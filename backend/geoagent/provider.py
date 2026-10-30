"""Chat Completions adapter and redacted, actionable provider diagnostics."""
from __future__ import annotations
import os
import re
from urllib.parse import urlparse
import httpx


def resolve_config(base_url, model, api_key):
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
    return {'base_url':base,'model':name,'api_key':key}


def completion_payload(config, messages, tools):
    model=config['model']
    reasoning_model=bool(re.match(r'^(?:gpt-[5-9](?:[.\-]|$)|o[1-9](?:[.\-]|$))',model))
    official=urlparse(config['base_url']).hostname=='api.openai.com'
    payload={'model':model,'messages':messages,'tools':tools}
    if official or reasoning_model:
        payload['max_completion_tokens']=2000
    else:
        payload['max_tokens']=2000
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
    # Explicit user action only. No workspace data or history is sent.
    payload=completion_payload(config,[{'role':'user','content':'请只回复 OK。'}],tools)
    payload['tool_choice']='none'
    with httpx.Client(timeout=httpx.Timeout(45,connect=10),follow_redirects=False) as client:
        data=request_completion(client,config,payload)
    note='当前接口以非推理模式调用该模型的工具。' if payload.get('reasoning_effort')=='none' else ''
    return {'ok':True,'model':data.get('model',config['model']),
            'message':'连接成功：模型请求及工具参数已被服务接受。'+note+'此测试未读取地理数据，也未运行 GIS 工具。'}
