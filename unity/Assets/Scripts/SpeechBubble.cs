using UnityEngine;

namespace PuebloVivo
{
    /// <summary>
    /// A world-space text label above an agent's head that shows the latest line for
    /// a few seconds and always faces the camera.
    /// </summary>
    public class SpeechBubble : MonoBehaviour
    {
        private TextMesh _text;
        private float _hideAt;
        private Camera _cam;

        public static SpeechBubble Attach(GameObject host, float height)
        {
            var go = new GameObject("SpeechBubble");
            go.transform.SetParent(host.transform, false);
            go.transform.localPosition = new Vector3(0, height, 0);
            var tm = go.AddComponent<TextMesh>();
            tm.characterSize = 0.12f;
            tm.fontSize = 64;
            tm.anchor = TextAnchor.LowerCenter;
            tm.alignment = TextAlignment.Center;
            tm.color = Color.white;
            var bubble = go.AddComponent<SpeechBubble>();
            bubble._text = tm;
            tm.text = "";
            return bubble;
        }

        private void Start() => _cam = Camera.main;

        public void Show(string line, float seconds = 6f)
        {
            if (_text == null) return;
            _text.text = Wrap(line, 28);
            _hideAt = Time.time + seconds;
        }

        private void LateUpdate()
        {
            if (_text == null) return;
            if (Time.time > _hideAt && _text.text.Length > 0) _text.text = "";
            if (_cam == null) _cam = Camera.main;
            if (_cam != null)
                transform.rotation = Quaternion.LookRotation(transform.position - _cam.transform.position);
        }

        private static string Wrap(string s, int width)
        {
            if (string.IsNullOrEmpty(s) || s.Length <= width) return s;
            var sb = new System.Text.StringBuilder();
            int lineLen = 0;
            foreach (var word in s.Split(' '))
            {
                if (lineLen + word.Length > width) { sb.Append('\n'); lineLen = 0; }
                sb.Append(word).Append(' ');
                lineLen += word.Length + 1;
            }
            return sb.ToString().TrimEnd();
        }
    }
}
