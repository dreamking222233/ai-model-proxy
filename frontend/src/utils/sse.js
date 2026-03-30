/**
 * SSE streaming utility for AI chat
 * Supports both OpenAI (/v1/chat/completions) and Anthropic (/v1/messages) protocols
 */

/**
 * Send a streaming chat completion request
 * @param {Object} options
 * @param {string} options.apiKey - User's API key (Bearer token)
 * @param {string} options.model - Model name
 * @param {Array} options.messages - Chat messages array [{role, content}]
 * @param {string} [options.apiType] - "openai" or "anthropic" (default: "openai")
 * @param {Function} options.onMessage - Callback for each delta chunk: (deltaText) => void
 * @param {Function} options.onDone - Callback when stream ends: (fullText) => void
 * @param {Function} options.onError - Callback on error: (error) => void
 * @param {AbortController} [options.controller] - Optional AbortController
 * @returns {AbortController}
 */
export function streamChat(options) {
  var apiKey = options.apiKey
  var model = options.model
  var messages = options.messages
  var apiType = options.apiType || 'openai'
  var onMessage = options.onMessage
  var onDone = options.onDone
  var onError = options.onError
  var controller = options.controller || new AbortController()

  var baseURL = process.env.NODE_ENV === 'production' ? 'https://api.xiaoleai.team' : ''

  if (apiType === 'anthropic') {
    _streamAnthropic(baseURL, apiKey, model, messages, onMessage, onDone, onError, controller)
  } else {
    _streamOpenAI(baseURL, apiKey, model, messages, onMessage, onDone, onError, controller)
  }

  return controller
}

/**
 * OpenAI protocol: POST /v1/chat/completions
 * SSE format: data: {"choices":[{"delta":{"content":"..."}}]}
 */
function _streamOpenAI(baseURL, apiKey, model, messages, onMessage, onDone, onError, controller) {
  var url = baseURL + '/v1/chat/completions'
  var fullText = ''
  var done = false

  fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + apiKey
    },
    body: JSON.stringify({
      model: model,
      messages: messages,
      stream: true
    }),
    signal: controller.signal
  })
    .then(function (response) {
      if (!response.ok) {
        return _handleErrorResponse(response)
      }

      var reader = response.body.getReader()
      var decoder = new TextDecoder('utf-8')
      var buffer = ''

      function processLines(lines) {
        for (var i = 0; i < lines.length; i++) {
          var line = lines[i].trim()
          if (!line || !line.startsWith('data: ')) continue
          var data = line.slice(6)
          if (data === '[DONE]') { done = true; return }
          try {
            var parsed = JSON.parse(data)
            var delta = parsed.choices && parsed.choices[0] && parsed.choices[0].delta
            if (delta && delta.content) {
              fullText += delta.content
              if (onMessage) onMessage(delta.content)
            }
          } catch (e) { /* skip */ }
        }
      }

      function read() {
        reader.read().then(function (result) {
          if (result.done || done) {
            if (buffer.trim()) processLines(buffer.split('\n'))
            if (onDone) onDone(fullText)
            return
          }
          buffer += decoder.decode(result.value, { stream: true })
          var lines = buffer.split('\n')
          buffer = lines.pop() || ''
          processLines(lines)
          if (done) { if (onDone) onDone(fullText); return }
          setTimeout(read, 0)
        }).catch(function (err) {
          if (err.name === 'AbortError') { if (onDone) onDone(fullText); return }
          if (onError) onError(err)
        })
      }

      read()
    })
    .catch(function (err) {
      if (err.name === 'AbortError') { if (onDone) onDone(fullText); return }
      if (onError) onError(err)
    })
}

/**
 * Anthropic protocol: POST /v1/messages
 * SSE format: event: content_block_delta + data: {"delta":{"text":"..."}}
 */
function _streamAnthropic(baseURL, apiKey, model, messages, onMessage, onDone, onError, controller) {
  var url = baseURL + '/v1/messages'
  var fullText = ''
  var done = false

  // Convert OpenAI-style messages to Anthropic format
  var systemPrompt = ''
  var anthropicMessages = []
  for (var i = 0; i < messages.length; i++) {
    var msg = messages[i]
    if (msg.role === 'system') {
      systemPrompt += (systemPrompt ? '\n' : '') + msg.content
    } else {
      anthropicMessages.push({
        role: msg.role === 'assistant' ? 'assistant' : 'user',
        content: msg.content
      })
    }
  }

  var body = {
    model: model,
    messages: anthropicMessages,
    max_tokens: 8192,
    stream: true
  }
  if (systemPrompt) {
    body.system = systemPrompt
  }

  fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01'
    },
    body: JSON.stringify(body),
    signal: controller.signal
  })
    .then(function (response) {
      if (!response.ok) {
        return _handleErrorResponse(response)
      }

      var reader = response.body.getReader()
      var decoder = new TextDecoder('utf-8')
      var buffer = ''
      var currentEvent = ''

      function processLines(lines) {
        for (var i = 0; i < lines.length; i++) {
          var line = lines[i].trim()
          if (!line) { currentEvent = ''; continue }

          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
            continue
          }

          if (line.startsWith('data: ')) {
            var data = line.slice(6)
            try {
              var parsed = JSON.parse(data)

              // content_block_delta → extract text
              if (currentEvent === 'content_block_delta' || parsed.type === 'content_block_delta') {
                var delta = parsed.delta
                if (delta && (delta.text || delta.text === '')) {
                  if (delta.text) {
                    fullText += delta.text
                    if (onMessage) onMessage(delta.text)
                  }
                }
              }

              // message_stop → done
              if (currentEvent === 'message_stop' || parsed.type === 'message_stop') {
                done = true
                return
              }

              // error event
              if (currentEvent === 'error' || parsed.type === 'error') {
                var errMsg = (parsed.error && parsed.error.message) || parsed.message || 'Anthropic stream error'
                if (onError) onError(new Error(errMsg))
                done = true
                return
              }
            } catch (e) { /* skip */ }
          }
        }
      }

      function read() {
        reader.read().then(function (result) {
          if (result.done || done) {
            if (buffer.trim()) processLines(buffer.split('\n'))
            if (onDone) onDone(fullText)
            return
          }
          buffer += decoder.decode(result.value, { stream: true })
          var lines = buffer.split('\n')
          buffer = lines.pop() || ''
          processLines(lines)
          if (done) { if (onDone) onDone(fullText); return }
          setTimeout(read, 0)
        }).catch(function (err) {
          if (err.name === 'AbortError') { if (onDone) onDone(fullText); return }
          if (onError) onError(err)
        })
      }

      read()
    })
    .catch(function (err) {
      if (err.name === 'AbortError') { if (onDone) onDone(fullText); return }
      if (onError) onError(err)
    })
}

/**
 * Handle non-OK HTTP response and throw a descriptive Error
 */
function _handleErrorResponse(response) {
  return response.text().then(function (text) {
    var errMsg = '请求失败 (' + response.status + ')'
    try {
      var errData = JSON.parse(text)
      errMsg = (errData.error && errData.error.message) || errData.message || errData.detail || errMsg
    } catch (e) { /* ignore */ }
    throw new Error(errMsg)
  })
}
