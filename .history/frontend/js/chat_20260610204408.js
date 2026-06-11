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
          // 明确告诉 Agent：用户位置坐标，并请求搜索周边 POI（加油站、餐厅、停车场等实用信息）
          var query = '我的当前位置坐标是 ' + coords + '。请帮我搜索这个位置周边 2 公里范围内的加油站、餐厅、停车场等实用地点。';
          $('chatInput').value = query;
          sendMessage();
        },
        function(err) {
          addMessage('assistant', '无法获取你的位置（' + err.message + '）。你可以直接告诉我你所在的位置（如"从北京市朝阳区出发..."）');
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 }
      );
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
      if (data.routes && data.routes.length > 0) {
        if (data.routes[0].type === 'route') {
          drawRoutesOnMap(data.routes);
        } else if (data.routes[0].type === 'poi') {
          drawPOIsOnMap(data.routes);
        }
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
