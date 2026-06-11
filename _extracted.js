
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

    // ===== 图片上传 =====
    function handleImageUpload(e) {
      var file = e.target.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function(ev) {
        state.selectedImage = ev.target.result;
        $('previewImg').src = ev.target.result;
        $('imagePreview').style.display = 'flex';
      };
      reader.readAsDataURL(file);
    }

    function removeImage() {
      state.selectedImage = null;
      $('imagePreview').style.display = 'none';
      $('imageInput').value = '';
    }

    function handleKeyDown(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    }

    // ===== 浏览器定位 =====
    function getUserLocation() {
      if (!navigator.geolocation) {
        addMessage('assistant', '你的浏览器不支持定位功能，你可以直接告诉我你所在的位置（如"从北京市朝阳区出发..."）');
        return;
      }
      navigator.geolocation.getCurrentPosition(
        function(pos) {
          var lng = pos.coords.longitude;
          var lat = pos.coords.latitude;
          var coords = lng.toFixed(6) + ',' + lat.toFixed(6);
          state.userLocation = coords;
          var query = '我当前的位置坐标是 ' + coords + '（经度 ' + lng.toFixed(4) + '，纬度 ' + lat.toFixed(4) + '），请帮我以这里为出发点规划路线或查询周边信息';
          addMessage('user', query);
          sendMessage();
        },
        function(err) {
          addMessage('assistant', '无法获取你的位置（' + err.message + '）。你可以直接告诉我你所在的位置（如"从北京市朝阳区出发..."）');
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 }
      );
    }

    // ===== 地图相关 =====
    function toggleMap() {
      var panel = $('mapPanel');
      var btn = $('mapToggleBtn');
      if (panel.classList.contains('visible')) {
        hideMap();
      } else {
        showMap();
      }
    }

    function showMap() {
      var panel = $('mapPanel');
      panel.classList.add('visible');
      panel.style.height = '380px';
      $('mapToggleBtn').classList.add('active');
      setTimeout(function() {
        if (!state.map) initMap();
        else if (state.map && typeof state.map.setFitView === 'function') {
          try { state.map.setFitView(); } catch (e) {}
        }
      }, 400);
    }

    function hideMap() {
      $('mapPanel').classList.remove('visible');
      $('mapPanel').style.height = '';
      $('mapToggleBtn').classList.remove('active');
    }

    function initMap() {
      if (!window.AMap) {
        console.warn('AMap JS 尚未加载，稍后重试');
        setTimeout(initMap, 500);
        return;
      }
      var container = $('mapContainer');
      if (!container || container.clientHeight < 50) {
        console.warn('地图容器尺寸不足，稍后重试');
        setTimeout(initMap, 500);
        return;
      }
      try {
        state.map = new AMap.Map(container, {
          zoom: 11,
          center: [116.397428, 39.90923],
          resizeEnable: true
        });
        state.map.addControl(new AMap.Scale());
        state.map.addControl(new AMap.ToolBar({ liteStyle: true }));
        console.log('[地图] 初始化成功');
      } catch (e) {
        console.error('[地图] 初始化失败:', e);
      }
    }

    function clearMap() {
      if (state.map && state.mapPolylines && state.mapPolylines.length) {
        try { state.map.remove(state.mapPolylines); } catch (e) {
          state.mapPolylines.forEach(function(p) { try { p.setMap(null); } catch (err) {} });
        }
      }
      if (state.map && state.mapMarkers && state.mapMarkers.length) {
        try { state.map.remove(state.mapMarkers); } catch (e) {
          state.mapMarkers.forEach(function(m) { try { m.setMap(null); } catch (err) {} });
        }
      }
      state.mapPolylines = [];
      state.mapMarkers = [];
      state.currentRoutes = null;
      var legend = $('mapLegend');
      if (legend) legend.style.display = 'none';
    }

    function parseCoord(s) {
      if (!s || typeof s !== 'string') return null;
      var parts = s.split(',');
      if (parts.length < 2) return null;
      var lng = parseFloat(parts[0]);
      var lat = parseFloat(parts[1]);
      if (isNaN(lng) || isNaN(lat)) return null;
      return [lng, lat];
    }

    function parsePolyline(route) {
      if (route.decoded_polyline && Array.isArray(route.decoded_polyline) && route.decoded_polyline.length >= 2) {
        var first = route.decoded_polyline[0];
        if (Array.isArray(first) && first.length >= 2 && typeof first[0] === 'number') {
          return route.decoded_polyline;
        }
        // 兼容 [[lng, lat], ...] 但元素是字符串
        if (Array.isArray(first) && first.length >= 2) {
          try {
            return route.decoded_polyline.map(function (pt) {
              return [parseFloat(pt[0]), parseFloat(pt[1])];
            });
          } catch (e) {}
        }
      }
      if (route.polyline && typeof route.polyline === 'string' && route.polyline.length > 10) {
        var raw = route.polyline;
        if (raw.indexOf(';') >= 0 && raw.indexOf(',') >= 0) {
          var path = [];
          var pairs = raw.split(';');
          for (var k = 0; k < pairs.length; k++) {
            if (!pairs[k]) continue;
            var ps = pairs[k].split(',');
            if (ps.length >= 2) {
              var lng = parseFloat(ps[0]);
              var lat = parseFloat(ps[1]);
              if (!isNaN(lng) && !isNaN(lat)) path.push([lng, lat]);
            }
          }
          if (path.length >= 2) return path;
        }
      }
      return null;
    }

    function drawRoutesOnMap(routes) {
      if (!routes || !Array.isArray(routes)) return;
      console.log('[地图] 绘制 ' + routes.length + ' 条路线');
      if (routes.length > 0 && routes[0]) {
        console.log('[地图] 第1条路线概览: origin=' + routes[0].origin_coord + ', dest=' + routes[0].dest_coord + ', decoded_polyline 长度=' +
          (routes[0].decoded_polyline && routes[0].decoded_polyline.length) + ', polyline=' + (routes[0].polyline ? '存在(' + routes[0].polyline.substring(0, 30) + '...)' : '无');
      }

      if (!window.AMap) {
        console.log('[地图] 等待 AMap JS 加载...');
        showMap();
        setTimeout(function() { if (window.AMap) drawRoutesOnMap(routes); }, 800);
        return;
      }

      showMap();

      if (!state.map) {
        setTimeout(function() {
          if (!state.map) initMap();
          setTimeout(function() { if (state.map) drawRoutesOnMap(routes); }, 300);
        }, 300);
        return;
      }

      clearMap();
      state.currentRoutes = routes;
      $('mapLegend').style.display = 'flex';

      var colors = ['#409eff', '#67c23a', '#e6a23c'];
      var allPoints = [];
      var originCoord = null, destCoord = null;
      var routeCount = 0;

      for (var idx = 0; idx < routes.length; idx++) {
        var route = routes[idx];
        if (!route || route.type !== 'route') continue;

        if (!originCoord) originCoord = parseCoord(route.origin_coord);
        if (!destCoord) destCoord = parseCoord(route.dest_coord);

        var path = parsePolyline(route);
        if (!path || path.length < 2) {
          console.warn('[地图] 路线 ' + idx + ' 无有效 polyline');
          continue;
        }

        try {
          var color = colors[routeCount % colors.length];
          var poly = new AMap.Polyline({
            path: path,
            strokeColor: color,
            strokeWeight: 7,
            strokeOpacity: 0.9,
            lineJoin: 'round',
            showDir: true,
            zIndex: 100 - routeCount
          });
          poly.setMap(state.map);
          state.mapPolylines.push(poly);
          allPoints = allPoints.concat(path);
          routeCount++;
        } catch (e) {
          console.error('[地图] 绘制路线 ' + idx + ' 失败:', e);
        }
      }

      if (originCoord) {
        var om = new AMap.Marker({
          position: originCoord,
          content: '<div style="background:#409eff;color:#fff;padding:4px 10px;border-radius:12px;font-size:13px;font-weight:bold;box-shadow:0 2px 6px rgba(0,0,0,0.3);">起点</div>',
          offset: new AMap.Pixel(-30, -12),
          zIndex: 200
        });
        om.setMap(state.map);
        state.mapMarkers.push(om);
      }
      if (destCoord) {
        var dm = new AMap.Marker({
          position: destCoord,
          content: '<div style="background:#f56c6c;color:#fff;padding:4px 10px;border-radius:12px;font-size:13px;font-weight:bold;box-shadow:0 2px 6px rgba(0,0,0,0.3);">终点</div>',
          offset: new AMap.Pixel(-30, -12),
          zIndex: 200
        });
        dm.setMap(state.map);
        state.mapMarkers.push(dm);
      }

      if (allPoints.length > 0) {
        try { state.map.setFitView(null, false, [60, 60, 60, 60]); }
        catch (e) { console.error('[地图] setFitView 失败:', e); }
      } else if (originCoord && destCoord) {
        try { state.map.setFitView(state.mapMarkers, false, [60, 60, 60, 60]); }
        catch (e) {
          try {
            var bounds = new AMap.Bounds(
              [Math.min(originCoord[0], destCoord[0]), Math.min(originCoord[1], destCoord[1])],
              [Math.max(originCoord[0], destCoord[0]), Math.max(originCoord[1], destCoord[1])]
            );
            state.map.setBounds(bounds);
          } catch (e2) {}
        }
      }
      console.log('[地图] 绘制完成，路线: ' + routeCount + '，总坐标点: ' + allPoints.length);
    }

    // ===== 路线选择卡片 =====
    function renderRouteSelection(data) {
      var container = $('routeSelection');
      var list = $('routeList');
      var title = $('routeSelectionTitle');
      title.innerHTML = '&#x1F50D; ' + (data.message || '请选择一条路线');

      list.innerHTML = data.routes.map(function(r, i) {
        if (r.type === 'route') {
          return '<div class="route-card' + (r.id === data.recommended_id ? ' recommended' : '') + '" ' +
            'onclick="selectRoute(\'' + r.id + '\')" ' +
            'onmouseenter="highlightRoute(' + i + ')" onmouseleave="unhighlightRoutes()">' +
            '<div class="route-info">' +
              '<div class="route-summary">' + (r.summary || '路线') + '</div>' +
              '<div class="route-tags">' +
                '<span class="tag">&#x1F697; ' + formatDist(r.distance) + '</span>' +
                '<span class="tag">&#x23F1; ' + formatDur(r.duration) + '</span>' +
              '</div>' +
            '</div>' +
            (r.id === data.recommended_id ? '<span class="badge">推荐</span>' : '') +
          '</div>';
        }
        return '<div class="route-card" onclick="selectRoute(\'' + r.id + '\')">' +
          '<span style="font-size:26px;">&#x1F4CD;</span>' +
          '<div class="poi-card">' +
            '<div class="poi-name">' + (r.name || '') + '</div>' +
            '<div class="poi-addr">' + (r.address || '') + '</div>' +
            '<div class="route-tags">' +
              (r.distance ? '<span class="tag">&#x1F4CF; ' + formatDist(r.distance) + '</span>' : '') +
              (r.rating ? '<span class="tag">&#x2B50; ' + r.rating + '</span>' : '') +
            '</div>' +
          '</div>' +
        '</div>';
      }).join('');

      container.style.display = 'block';
      // 同步绘制地图
      if (data.routes && data.routes.length > 0 && data.routes[0].type === 'route') {
        drawRoutesOnMap(data.routes);
      }
      setTimeout(scrollToBottom, 50);
    }

    function highlightRoute(idx) {
      if (!state.mapPolylines || !state.mapPolylines.length) return;
      state.mapPolylines.forEach(function(p, i) {
        try { p.setOptions({ strokeWeight: i === idx ? 10 : 5, strokeOpacity: i === idx ? 1 : 0.5 }); }
        catch (e) {}
      });
      var cards = document.querySelectorAll('#routeList .route-card');
      cards.forEach(function(c, i) { c.classList.toggle('selected', i === idx); });
    }

    function unhighlightRoutes() {
      if (!state.mapPolylines || !state.mapPolylines.length) return;
      state.mapPolylines.forEach(function(p) {
        try { p.setOptions({ strokeWeight: 7, strokeOpacity: 0.9 }); }
        catch (e) {}
      });
      var cards = document.querySelectorAll('#routeList .route-card');
      cards.forEach(function(c) { c.classList.remove('selected'); });
    }

    // ===== 选择路线 =====
    async function selectRoute(routeId) {
      if (!state.sessionId) return;
      state.isLoading = true;
      $('loadingIndicator').style.display = 'flex';
      $('routeSelection').style.display = 'none';

      try {
        var res = await fetch('/api/select-route', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: state.sessionId, selected_route_id: routeId })
        });
        var data = await res.json();
        if (data.response) addMessage('assistant', data.response);
        saveHistory();
      } catch (err) {
        addMessage('assistant', '选择路线时出错: ' + err.message);
      } finally {
        state.isLoading = false;
        $('loadingIndicator').style.display = 'none';
      }
    }

    // ===== 发送消息 =====
    async function sendMessage() {
      var input = $('chatInput');
      if (!input) { console.error('找不到 chatInput'); return; }
      var query = input.value.trim();
      if (!query && !state.selectedImage) return;

      var imageBase64 = state.selectedImage ? state.selectedImage.split(',')[1] : null;

      console.log('[发送消息] query=' + query + ', has_image=' + (!!imageBase64));
      addMessage('user', query || '[图片]');
      $('welcomeMessage').style.display = 'none';
      input.value = '';
      removeImage();

      state.isLoading = true;
      state.routeSelection = null;
      state.assistantMsgIndex = -1;
      state.fullContent = '';
      var routeSel = $('routeSelection');
      if (routeSel) routeSel.style.display = 'none';
      var loading = $('loadingIndicator');
      if (loading) loading.style.display = 'flex';
      var sendBtn = $('sendBtn');
      if (sendBtn) sendBtn.disabled = true;

      try {
        var res = await fetch('/api/chat/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_query: query, image_base64: imageBase64, session_id: state.sessionId })
        });

        if (!res.ok) {
          var errText = await res.text().catch(function() { return ''; });
          throw new Error('HTTP ' + res.status + ' ' + (errText.substring(0, 200) || res.statusText));
        }

        var reader = res.body.getReader();
        var decoder = new TextDecoder('utf-8');
        var buffer = '';

        while (true) {
          var result = await reader.read();
          if (result.done) break;

          buffer += decoder.decode(result.value, { stream: true });

          while (buffer.indexOf('\n\n') >= 0) {
            var idx = buffer.indexOf('\n\n');
            var event = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);

            if (event.indexOf('data: ') !== 0) continue;

            try {
              var data = JSON.parse(event.slice(6));

              if (data.type === 'stream') {
                state.fullContent += data.content;
                if (state.assistantMsgIndex === -1) {
                  state.messages.push({ role: 'assistant', content: safeMarked(state.fullContent), time: getTime() });
                  state.assistantMsgIndex = state.messages.length - 1;
                } else {
                  updateLastMessage(state.fullContent);
                }
              } else if (data.type === 'end') {
                if (data.session_id) state.sessionId = data.session_id;
                if (data.routes && data.routes.length > 0 && data.routes[0].type === 'route') {
                  drawRoutesOnMap(data.routes);
                }
                saveHistory();
                state.isLoading = false;
              } else if (data.type === 'pending_selection') {
                if (data.session_id) state.sessionId = data.session_id;
                state.routeSelection = data.data;
                addMessage('assistant', data.message);
                renderRouteSelection(data.data);
                saveHistory();
                state.isLoading = false;
              } else if (data.type === 'error') {
                addMessage('assistant', data.content);
                state.isLoading = false;
              }
            } catch (e) {
              console.error('解析 SSE 事件失败:', e, event.substring(0, 200));
            }
          }
        }
        console.log('[发送消息] 完成，最终内容长度=' + (state.fullContent ? state.fullContent.length : 0));
      } catch (err) {
        console.error('[发送消息] 错误:', err);
        addMessage('assistant', '❌ 请求失败: ' + err.message);
      } finally {
        state.isLoading = false;
        var loading2 = $('loadingIndicator');
        if (loading2) loading2.style.display = 'none';
        var sendBtn2 = $('sendBtn');
        if (sendBtn2) sendBtn2.disabled = false;
      }
    }

    // ===== 地图拖拽调整大小 =====
    (function() {
      var handle = $('resizeHandle');
      var panel = $('mapPanel');
      var isResizing = false;
      var startY, startHeight;

      handle.addEventListener('mousedown', function(e) {
        isResizing = true;
        startY = e.clientY;
        startHeight = panel.offsetHeight;
        document.body.style.cursor = 'ns-resize';
        document.body.style.userSelect = 'none';
        e.preventDefault();
      });

      document.addEventListener('mousemove', function(e) {
        if (!isResizing) return;
        var newHeight = startHeight + (e.clientY - startY);
        if (newHeight >= 150 && newHeight <= 600) {
          panel.style.height = newHeight + 'px';
        }
      });

      document.addEventListener('mouseup', function() {
        if (isResizing) {
          isResizing = false;
          document.body.style.cursor = '';
          document.body.style.userSelect = '';
          if (state.map) state.map.setFitView();
        }
      });
    })();

    // ===== 页面加载时恢复历史会话 =====
    (function() {
      loadHistory();
    })();
  