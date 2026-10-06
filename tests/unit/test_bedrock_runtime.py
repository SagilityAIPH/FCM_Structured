import json

import httpx
import pytest
from types import SimpleNamespace

from AI import bedrock_runtime as runtime
from AI import bedrock_core as core
from AI.batch_samples import _make_llm_call
from tests.unit.test_referral_schema import complete_payload


def test_default_extraction_sends_16k_budget():
    def handle(request):
        assert json.loads(request.content)['inferenceConfig']['maxTokens'] == 16384
        return httpx.Response(200, json={
            'stopReason': 'end_turn',
            'output': {'message': {'content': [{'text': json.dumps(complete_payload())}]}},
        })

    with runtime.RuntimeClient('test-token', runtime.build_bedrock_base_url('us-east-2'),
                               transport=httpx.MockTransport(handle)) as client:
        _, fields, _, _ = runtime.run_reasoning(client, runtime.DEFAULT_BEDROCK_MODEL, 'Sample')
        assert fields['First Name'] == complete_payload()['First Name']


@pytest.mark.parametrize('answer', ['', json.dumps(complete_payload())])
def test_token_limit_stop_rejects_even_parseable_partial_answer(answer):
    def handle(request):
        return httpx.Response(200, json={
            'stopReason': 'max_tokens',
            'output': {'message': {'content': [{'text': answer}]}},
        })

    with runtime.RuntimeClient('test-token', runtime.build_bedrock_base_url('us-east-2'),
                               transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(RuntimeError, match=r'output token limit \(16,384\)'):
            runtime.run_reasoning(client, runtime.DEFAULT_BEDROCK_MODEL, 'Sample')


@pytest.mark.parametrize('transport', ['mantle', 'batch'])
def test_other_transports_reject_token_limit_stop(transport):
    if transport == 'mantle':
        response = SimpleNamespace(choices=[SimpleNamespace(
            finish_reason='length', message=SimpleNamespace(content='{}'))])
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: response)))
        invoke = core.call_llm_once
    else:
        client = SimpleNamespace(converse=lambda **_: {'stopReason': 'max_tokens'})
        invoke = _make_llm_call()
    with pytest.raises(RuntimeError, match='Increase Output tokens to 16,384'):
        invoke(client=client, model_id='test', prompt='Sample', max_tokens=8192, temperature=0.0)


def test_runtime_converse_request_and_response():
    def handle(request):
        assert request.url.host == 'bedrock-runtime.us-east-2.amazonaws.com'
        assert request.url.path == '/model/openai.gpt-oss-120b-1:0/converse'
        assert request.headers['Authorization'] == 'Bearer test-token'
        body = json.loads(request.content)
        assert body['system'] == [{'text': 'Extract fields'}]
        assert body['messages'] == [{'role': 'user', 'content': [{'text': 'Sample document'}]}]
        assert body['inferenceConfig'] == {'maxTokens': 768, 'temperature': 0.0, 'topP': 0.4}
        return httpx.Response(200, json={'output': {'message': {'content': [
            {'reasoningContent': {'reasoningText': {'text': 'not an answer'}}},
            {'text': 'Provider Phone: 212-555-1234'}, {'text': 'NCM: Not found'},
        ]}}})
    with runtime.RuntimeClient('test-token', runtime.build_bedrock_base_url('us-east-2'),
                               transport=httpx.MockTransport(handle)) as client:
        result = client.chat.completions.create(model=runtime.DEFAULT_BEDROCK_MODEL,
            messages=[{'role': 'system', 'content': 'Extract fields'}, {'role': 'user', 'content': 'Sample document'}],
            max_completion_tokens=768, temperature=0.0, top_p=0.4)
        assert result.choices[0].message.content == 'Provider Phone: 212-555-1234\nNCM: Not found'


def test_connection_uses_runtime_converse():
    def handle(request):
        assert request.url.host == 'bedrock-runtime.us-east-2.amazonaws.com'
        body = json.loads(request.content)
        assert body['messages'][0]['content'][0]['text'] == 'Reply with exactly: BEDROCK_OK'
        return httpx.Response(200, json={'output': {'message': {'content': [{'text': 'BEDROCK_OK'}]}}})
    with runtime.RuntimeClient('test-token', runtime.build_bedrock_base_url('us-east-2'),
                               transport=httpx.MockTransport(handle)) as client:
        assert runtime.test_bedrock_connection(client, runtime.DEFAULT_BEDROCK_MODEL) == 'BEDROCK_OK'


def test_access_error_is_reported_without_key():
    with runtime.RuntimeClient('test-token', runtime.build_bedrock_base_url('us-east-2'),
            transport=httpx.MockTransport(lambda request: httpx.Response(403, text='denied test-token'))) as client:
        with pytest.raises(RuntimeError, match='Runtime HTTP 403') as error:
            runtime.test_bedrock_connection(client, runtime.DEFAULT_BEDROCK_MODEL)
        assert 'test-token' not in str(error.value)


def test_empty_response_is_not_reported_as_success():
    with runtime.RuntimeClient('test-token', runtime.build_bedrock_base_url('us-east-2'),
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))) as client:
        with pytest.raises(RuntimeError, match='no answer text'):
            runtime.test_bedrock_connection(client, runtime.DEFAULT_BEDROCK_MODEL)


def test_key_priority(monkeypatch):
    monkeypatch.setenv('AWS_BEARER_TOKEN_BEDROCK', 'runtime-key')
    monkeypatch.setenv('OPENAI_API_KEY', 'old-key')
    assert runtime.resolve_bedrock_api_key() == 'runtime-key'
    assert runtime.resolve_bedrock_api_key('manual-key') == 'manual-key'
