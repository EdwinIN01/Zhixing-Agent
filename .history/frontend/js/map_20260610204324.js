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
          (routes[0].decoded_polyline && routes[0].decoded_polyline.length) + ', polyline=' + (routes[0].polyline ? '存在(' + routes[0].polyline.substring(0, 30) + '...)' : '无'));
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

    // ===== POI 标记 =====
    function drawPOIsOnMap(pois) {
      if (!pois || !Array.isArray(pois) || pois.length === 0) return;
      console.log('[地图] 绘制 ' + pois.length + ' 个 POI');

      if (!window.AMap) {
        showMap();
        setTimeout(function() { if (window.AMap) drawPOIsOnMap(pois); }, 800);
        return;
      }

      showMap();
      if (!state.map) {
        setTimeout(function() {
          if (!state.map) initMap();
          setTimeout(function() { if (state.map) drawPOIsOnMap(pois); }, 300);
        }, 300);
        return;
      }

      clearMap();
      state.currentRoutes = pois;

      var poiColors = ['#67c23a', '#409eff', '#e6a23c', '#f56c6c', '#909399'];
      var allPoints = [];
      var drawnCount = 0;

      for (var i = 0; i < pois.length; i++) {
        var poi = pois[i];
        if (!poi || poi.type !== 'poi') continue;

        var coord = parseCoord(poi.location);
        if (!coord) continue;

        try {
          var color = poiColors[drawnCount % poiColors.length];
          var label = String(drawnCount + 1);
          var marker = new AMap.Marker({
            position: coord,
            content: '<div style="background:' + color + ';color:#fff;padding:3px 9px;border-radius:10px;font-size:13px;font-weight:bold;box-shadow:0 2px 6px rgba(0,0,0,0.3);white-space:nowrap;">' +
              label + '. ' + (poi.name || 'POI').substring(0, 10) + '</div>',
            offset: new AMap.Pixel(-20, -12),
            zIndex: 150
          });
          marker.setMap(state.map);
          state.mapMarkers.push(marker);
          allPoints.push(coord);
          drawnCount++;
        } catch (e) {
          console.error('[地图] 绘制 POI ' + i + ' 失败:', e);
        }
      }

      if (allPoints.length > 0) {
        try { state.map.setFitView(null, false, [60, 60, 60, 60]); }
        catch (e) { console.error('[地图] setFitView 失败:', e); }
      }
      console.log('[地图] POI 绘制完成，数量: ' + drawnCount);
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