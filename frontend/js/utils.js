
    // ===== 状态 =====
    var state = {
      messages: [],
      sessionId: null,
      isLoading: false,
      selectedImage: null,
      routeSelection: null,
      assistantMsgIndex: -1,
      fullContent: '',
      currentRoutes: null,
      userLocation: null,
      map: null,
      mapPolylines: [],
      mapMarkers: []
    };

    var $ = function(id) { return document.getElementById(id); };
    var scrollToBottom = function() {
      var el = $('messagesScroll');
      setTimeout(function() { el.scrollTop = el.scrollHeight; }, 50);
    };

    function getTime() {
      var d = new Date();
      return String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0');
    }

    function formatDist(m) {
      if (!m) return '';
      return m >= 1000 ? (m/1000).toFixed(1)+' 公里' : m+' 米';
    }

    function formatDur(s) {
      if (!s) return '';
      var min = Math.floor(s/60);
      var h = Math.floor(min/60);
      return h > 0 ? h+' 小时 '+(min%60)+' 分钟' : min+' 分钟';
    }

    // ===== 消息渲染 =====
    function safeMarked(content) {
      try {
        if (window.marked && typeof marked.parse === 'function') {
          return marked.parse(content || '');
        }
      } catch (e) {}
      return String(content || '').replace(/\n/g, '<br/>');
    }

    function addMessage(role, content) {
      state.messages.push({ role: role, content: safeMarked(content), time: getTime() });
      renderMessages();
      scrollToBottom();
    }

    function updateLastMessage(content) {
      if (state.messages.length > 0) {
        state.messages[state.messages.length - 1].content = safeMarked(content);
        renderMessages();
        scrollToBottom();
      }
    }

    function renderMessages() {
      var list = $('messageList');
      list.innerHTML = state.messages.map(function(m) {
        return '<div class="message-item ' + m.role + '">' +
          '<div class="avatar ' + m.role + '">' + (m.role === 'user' ? '&#x1F464' : '&#x1F916') + '</div>' +
          '<div class="message-bubble">' +
            '<div class="message-content">' + m.content + '</div>' +
            '<div class="message-time">&#x1F550; ' + m.time + '</div>' +
          '</div>' +
        '</div>';
      }).join('');
    }
