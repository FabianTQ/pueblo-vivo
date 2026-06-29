using System;
using System.Collections.Concurrent;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace PuebloVivo
{
    /// <summary>
    /// WebSocket client to the Python brain. Receives on a background task and
    /// dispatches parsed events on Unity's main thread (Update), since Unity APIs
    /// are not thread-safe. Other components subscribe to <see cref="OnEvent"/>.
    /// </summary>
    public class BrainClient : MonoBehaviour
    {
        [Tooltip("WebSocket URL of the brain server.")]
        public string url = "ws://127.0.0.1:8765/ws";

        [Tooltip("Reconnect automatically if the socket drops.")]
        public bool autoReconnect = true;

        public event Action<JObject> OnEvent;
        public event Action OnConnected;
        public event Action OnDisconnected;

        public bool IsConnected => _socket != null && _socket.State == WebSocketState.Open;

        private ClientWebSocket _socket;
        private CancellationTokenSource _cts;
        private readonly ConcurrentQueue<JObject> _inbox = new ConcurrentQueue<JObject>();
        private readonly ConcurrentQueue<string> _outbox = new ConcurrentQueue<string>();

        private void OnEnable()
        {
            _cts = new CancellationTokenSource();
            _ = RunAsync(_cts.Token);
        }

        private void OnDisable()
        {
            _cts?.Cancel();
            try { _socket?.Abort(); } catch { /* ignore */ }
            _socket = null;
        }

        private void Update()
        {
            // Drain inbound events on the main thread.
            while (_inbox.TryDequeue(out var ev))
            {
                try { OnEvent?.Invoke(ev); }
                catch (Exception e) { Debug.LogError($"[BrainClient] handler error: {e}"); }
            }
        }

        // ---- public send helpers --------------------------------------
        public void Send(object message)
        {
            _outbox.Enqueue(JsonConvert.SerializeObject(message));
        }

        public void Pause() => Send(new { type = "time_control", action = "pause" });
        public void Resume() => Send(new { type = "time_control", action = "resume" });
        public void Step() => Send(new { type = "time_control", action = "step" });
        public void SetSpeed(float s) => Send(new { type = "time_control", action = "speed", speed = s });
        public void PlayerSay(string agent, string text) => Send(new { type = "player_say", agent, text });
        public void InjectEvent(string text, string location = null) => Send(new { type = "inject_event", text, location });
        public void Inspect(string agent) => Send(new { type = "inspect", agent });
        public void RequestSnapshot() => Send(new { type = "snapshot" });

        // ---- background socket loop ------------------------------------
        private async Task RunAsync(CancellationToken token)
        {
            while (!token.IsCancellationRequested)
            {
                try
                {
                    _socket = new ClientWebSocket();
                    await _socket.ConnectAsync(new Uri(url), token);
                    OnConnected?.Invoke();
                    _ = SendLoopAsync(token);
                    await ReceiveLoopAsync(token);
                }
                catch (OperationCanceledException) { break; }
                catch (Exception e)
                {
                    Debug.LogWarning($"[BrainClient] connection error: {e.Message}");
                }
                OnDisconnected?.Invoke();
                if (!autoReconnect || token.IsCancellationRequested) break;
                try { await Task.Delay(1500, token); } catch { break; }
            }
        }

        private async Task ReceiveLoopAsync(CancellationToken token)
        {
            var buffer = new byte[64 * 1024];
            var sb = new StringBuilder();
            while (_socket.State == WebSocketState.Open && !token.IsCancellationRequested)
            {
                WebSocketReceiveResult result;
                sb.Clear();
                do
                {
                    result = await _socket.ReceiveAsync(new ArraySegment<byte>(buffer), token);
                    if (result.MessageType == WebSocketMessageType.Close)
                    {
                        await _socket.CloseAsync(WebSocketCloseStatus.NormalClosure, "bye", token);
                        return;
                    }
                    sb.Append(Encoding.UTF8.GetString(buffer, 0, result.Count));
                } while (!result.EndOfMessage);

                var text = sb.ToString();
                if (string.IsNullOrWhiteSpace(text)) continue;
                try { _inbox.Enqueue(JObject.Parse(text)); }
                catch (Exception e) { Debug.LogWarning($"[BrainClient] bad JSON: {e.Message}"); }
            }
        }

        private async Task SendLoopAsync(CancellationToken token)
        {
            while (_socket != null && _socket.State == WebSocketState.Open && !token.IsCancellationRequested)
            {
                if (_outbox.TryDequeue(out var msg))
                {
                    var bytes = Encoding.UTF8.GetBytes(msg);
                    await _socket.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, token);
                }
                else
                {
                    try { await Task.Delay(20, token); } catch { break; }
                }
            }
        }
    }
}
