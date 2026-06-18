(function () {
  var data = window.COLLAGE_LAYOUT;
  var stage = document.getElementById("collageStage");
  var layer = document.getElementById("hotspotLayer");
  var image = document.getElementById("collageImage");
  
  // Mobile Menu Logic
  var menuBtn = document.getElementById("mobileMenuBtn");
  var menuOverlay = document.getElementById("mobileMenu");
  var menuClose = document.getElementById("mobileMenuClose");

  if (menuBtn && menuOverlay && menuClose) {
      menuBtn.addEventListener("click", function() {
          menuOverlay.classList.add("is-open");
      });
      menuClose.addEventListener("click", function() {
          menuOverlay.classList.remove("is-open");
      });
  }

  var fallbackWorldImage = image ? image.getAttribute("src") : "";

  if (image) {
    image.addEventListener("error", function () {
      if (fallbackWorldImage) image.src = fallbackWorldImage;
    });
  }

  if (!data) return;

  var isJp = location.pathname.startsWith("/jp/");
  var jpTitlesById = {
    mouthful: "川をひとくち",
    sik: "コンゴの宇宙飛行士",
    mulika: "ムリカ",
    sij: "日曜日の日本",
    broadlistening: "ブロード・リスニング",
    arakawacats: "荒川の猫たち"
  };

  function projectTitle(project) {
    if (!isJp) return project.title;
    return jpTitlesById[project.id] || project.title;
  }

  var isSmall = window.matchMedia("(max-width: 768px)").matches;
  var armedId = "";
  var activeHotspot = null;
  var clearActiveTimer = 0;
  var lastPointer = { x: null, y: null };

  // Create single Desat Mask
  var desatMask = document.createElement("div");
  desatMask.className = "desat-mask";
  layer.appendChild(desatMask);
  
  // Create Callout Wrapper
  var calloutWrapper = document.createElement("div");
  calloutWrapper.className = "callout-wrapper";
  stage.appendChild(calloutWrapper);

  function pct(value) {
    return (value * 100).toFixed(6) + "%";
  }

  function setFocusWindowFromHotspot(hotspot) {
    layer.style.setProperty("--focus-left", hotspot.style.left || "0%");
    layer.style.setProperty("--focus-top", hotspot.style.top || "0%");
    layer.style.setProperty("--focus-width", hotspot.style.width || "0%");
    layer.style.setProperty("--focus-height", hotspot.style.height || "0%");
  }

  function setActive(hotspot) {
    if (clearActiveTimer) clearTimeout(clearActiveTimer);
    if (activeHotspot === hotspot) return;
    
    if (activeHotspot) {
        activeHotspot.classList.remove("is-active");
        if (activeHotspot._callout) activeHotspot._callout.classList.remove("is-active");
    }
    
    activeHotspot = hotspot || null;
    
    if (activeHotspot) {
      activeHotspot.classList.add("is-active");
      if (activeHotspot._callout) activeHotspot._callout.classList.add("is-active");
      setFocusWindowFromHotspot(activeHotspot);
      layer.classList.add("has-active");
    } else {
      layer.classList.remove("has-active");
    }
  }

  function isProjectTarget(target, hotspot) {
    return !!(
      target &&
      hotspot &&
      (hotspot.contains(target) || (hotspot._callout && hotspot._callout.contains(target)))
    );
  }

  function pointerIsStillOnActiveProject() {
    if (!activeHotspot || lastPointer.x === null || lastPointer.y === null) return false;

    var target = document.elementFromPoint(lastPointer.x, lastPointer.y);
    return isProjectTarget(target, activeHotspot);
  }

  function queueClearActive(hotspot, event) {
    if (event && isProjectTarget(event.relatedTarget, hotspot || activeHotspot)) return;
    if (clearActiveTimer) clearTimeout(clearActiveTimer);

    clearActiveTimer = setTimeout(function () {
      if (pointerIsStillOnActiveProject()) return;
      setActive(null);
    }, 140);
  }

  function bindDesktopHover(target, hotspot) {
    target.addEventListener("pointerenter", function () { if (!isSmall) setActive(hotspot); });
    target.addEventListener("pointerleave", function (event) { if (!isSmall) queueClearActive(hotspot, event); });
    target.addEventListener("mouseenter", function () { if (!isSmall) setActive(hotspot); });
    target.addEventListener("mouseleave", function (event) { if (!isSmall) queueClearActive(hotspot, event); });
  }

  document.addEventListener("pointermove", function (event) {
    lastPointer.x = event.clientX;
    lastPointer.y = event.clientY;
  }, true);

  document.addEventListener("mousemove", function (event) {
    lastPointer.x = event.clientX;
    lastPointer.y = event.clientY;
  }, true);

  if (image && data.world_image) image.src = data.world_image;

  data.projects.forEach(function (project) {
    var hotspot = document.createElement("a");
    hotspot.className = "hotspot-v4";
    hotspot.href = project.url;
    hotspot.style.left = pct(project.x_pct);
    hotspot.style.top = pct(project.y_pct);
    hotspot.style.width = pct(project.width_pct);
    hotspot.style.height = pct(project.height_pct);

    var label = document.createElement("span");
    label.className = "hotspot-label";

    var title = document.createElement("span");
    title.className = "hotspot-title";
    title.textContent = projectTitle(project);

    var meta = document.createElement("span");
    meta.className = "hotspot-meta";
    meta.textContent = [project.year, project.status, project.role, project.runtime].filter(Boolean).join(" / ");

    var summary = document.createElement("span");
    summary.className = "hotspot-summary";
    summary.textContent = project.summary || "";

    label.appendChild(title);
    label.appendChild(meta);
    label.appendChild(summary);
    hotspot.appendChild(label);

    // Interaction handlers
    bindDesktopHover(hotspot, hotspot);
    hotspot.addEventListener("focus", function () { if (!isSmall) setActive(hotspot); });
    hotspot.addEventListener("blur", function (event) { if (!isSmall) queueClearActive(hotspot, event); });

    // Single click/tap navigation for all devices
    hotspot.addEventListener("click", function (event) {
        // No event.preventDefault() - let the link click happen naturally
    });

    layer.appendChild(hotspot);

    // Callout (Desktop)
    var callout = document.createElement("div");
    var centerX_pct = project.x_pct + (project.width_pct / 2);
    var isLeft = centerX_pct < 0.5;
    callout.className = isLeft ? "callout left" : "callout right";
    
    var centerY = project.y_pct + (project.height_pct / 2);
    callout.style.top = pct(centerY);
    
    var content = document.createElement("a");
    content.className = "callout-content";
    content.href = project.url;
    content.setAttribute("aria-label", projectTitle(project));

    var text = document.createElement("span");
    text.className = "callout-text";
    text.textContent = projectTitle(project);

    var calloutMeta = document.createElement("span");
    calloutMeta.className = "callout-meta";
    calloutMeta.textContent = [project.year, project.status, project.role, project.runtime].filter(Boolean).join(" / ");

    var calloutSummary = document.createElement("span");
    calloutSummary.className = "callout-summary";
    calloutSummary.textContent = project.summary || "";
    
    var line = document.createElement("span");
    line.className = "callout-line";

    content.appendChild(text);
    content.appendChild(calloutMeta);
    content.appendChild(calloutSummary);
    callout.appendChild(content);
    callout.appendChild(line);
    calloutWrapper.appendChild(callout);
    
    hotspot._callout = callout;

    bindDesktopHover(callout, hotspot);
    content.addEventListener("focus", function() { if (!isSmall) setActive(hotspot); });
    content.addEventListener("blur", function(event) { if (!isSmall) queueClearActive(hotspot, event); });
  });

  document.addEventListener("click", function (event) {
    if (!stage.contains(event.target) && !event.target.closest('.mobile-menu-btn')) {
      setActive(null);
    }
  });

})();
