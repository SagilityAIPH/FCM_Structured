import json

import httpx
import pytest

from AI import bedrock_runtime as runtime


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
