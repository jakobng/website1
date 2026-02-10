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
  var worldImageCandidates = [];

  function addCandidate(src) {
    if (!src) return;
    if (worldImageCandidates.indexOf(src) === -1) worldImageCandidates.push(src);
  }

  addCandidate(data && data.world_image);
  addCandidate(fallbackWorldImage);
  addCandidate("images/mouthful_still.jpg");
  addCandidate("images/broadlistening_still.jpg");

  if (image) {
    image.dataset.fallbackIndex = "0";
    image.addEventListener("error", function () {
      var nextIndex = Number(image.dataset.fallbackIndex || "0") + 1;
      image.dataset.fallbackIndex = String(nextIndex);
      if (worldImageCandidates[nextIndex]) image.src = worldImageCandidates[nextIndex];
    });
  }

  if (!data) return;

  var isSmall = window.matchMedia("(max-width: 768px)").matches;
  var armedId = "";
  var activeHotspot = null;
  var clearActiveTimer = 0;

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

  function queueClearActive() {
    clearActiveTimer = setTimeout(function () {
      setActive(null);
    }, 50);
  }

  if (image && worldImageCandidates[0]) image.src = worldImageCandidates[0];

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
    title.textContent = project.title;

    var meta = document.createElement("span");
    meta.className = "hotspot-meta";
    meta.textContent = project.year + " / " + project.role + " / " + project.runtime;

    var summary = document.createElement("span");
    summary.className = "hotspot-summary";
    summary.textContent = project.summary || "";

    label.appendChild(title);
    label.appendChild(meta);
    label.appendChild(summary);
    hotspot.appendChild(label);

    // Interaction handlers
    hotspot.addEventListener("mouseenter", function () { if (!isSmall) setActive(hotspot); });
    hotspot.addEventListener("mouseleave", function () { if (!isSmall) queueClearActive(); });
    hotspot.addEventListener("focus", function () { if (!isSmall) setActive(hotspot); });
    hotspot.addEventListener("blur", function () { if (!isSmall) queueClearActive(); });

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
    
    var text = document.createElement("span");
    text.className = "callout-text";
    text.textContent = project.title;
    
    var line = document.createElement("span");
    line.className = "callout-line";
    
    callout.appendChild(text);
    callout.appendChild(line);
    calloutWrapper.appendChild(callout);
    
    hotspot._callout = callout;

    text.addEventListener("mouseenter", function() { if (!isSmall) setActive(hotspot); });
    text.addEventListener("mouseleave", function() { if (!isSmall) queueClearActive(); });
    text.addEventListener("click", function(event) { 
        window.location.href = project.url; 
    });
  });

  document.addEventListener("click", function (event) {
    if (!stage.contains(event.target) && !event.target.closest('.mobile-menu-btn')) {
      setActive(null);
    }
  });

})();