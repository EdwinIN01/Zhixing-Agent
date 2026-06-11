    // ===== 新建对话 =====
    function startNewChat() {
      state.messages = [];
      state.sessionId = null;
      state.selectedImage = null;
      state.routeSelection = null;
      state.currentRoutes = null;
      state.userLocation = null;
      clearMap();
      hideMap();
      $('messageList').innerHTML = '';
      $('welcomeMessage').style.display = 'block';
      $('routeSelection').style.display = 'none';
      $('chatInput').value = '';
      removeImage();
      clearHistory();
    }

    function sendQuickMessage(msg) {
      $('chatInput').value = msg;
      sendMessage();
    }

    // ===== 历史会话持久化 =====
    var HISTORY_KEY = 'route_planner_history';

    function saveHistory() {
      try {
        var data = {
          messages: state.messages,
          sessionId: state.sessionId,
          currentRoutes: state.currentRoutes,
          updatedAt: new Date().toISOString()
        };
        localStorage.setItem(HISTORY_KEY, JSON.stringify(data));
      } catch (e) {
        console.warn('保存历史失败:', e);
      }
    }

    function loadHistory() {
      try {
        var raw = localStorage.getItem(HISTORY_KEY);
        if (!raw) return false;
        var data = JSON.parse(raw);

        // 恢复消息列表
        if (data.messages && Array.isArray(data.messages)) {
          state.messages = data.messages;
          renderMessages();
          $('welcomeMessage').style.display = 'none';
          scrollToBottom();
        }

        // 恢复 sessionId
        if (data.sessionId) {
          state.sessionId = data.sessionId;
        }

        // 恢复地图路线
        if (data.currentRoutes && Array.isArray(data.currentRoutes) && data.currentRoutes.length > 0) {
          setTimeout(function() {
            if (!state.map) showMap();
            setTimeout(function() {
              if (!state.map) initMap();
              drawRoutesOnMap(data.currentRoutes);
            }, 400);
          }, 100);
        }

        return true;
      } catch (e) {
        console.warn('加载历史失败:', e);
        return false;
      }
    }

    function clearHistory() {
      try {
        localStorage.removeItem(HISTORY_KEY);
      } catch (e) {
        console.warn('清除历史失败:', e);
      }
    }

    // ===== 页面加载时恢复历史会话 =====
    (function() {
      loadHistory();
    })();