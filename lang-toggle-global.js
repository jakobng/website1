(function () {
  var LANG_LABEL = "\u65e5\u672c\u8a9e";

  function targetForPage(file) {
    if (location.pathname.startsWith("/jp/")) {
      return "/" + file;
    }
    return "/jp/" + file;
  }

  function inferFile() {
    return location.pathname.split("/").filter(Boolean).pop() || "index.html";
  }

  function handleToggle(event) {
    event.preventDefault();
    var file = this.getAttribute("data-lang-file") || inferFile();
    location.href = targetForPage(file);
  }

  function initMobileMenu() {
    var topbar = document.querySelector(".cat-topbar, .film-topbar, .collage-header-v4");
    if (!topbar || document.querySelector(".mobile-menu-btn")) return;

    var menuBtn = document.createElement("button");
    menuBtn.className = "mobile-menu-btn";
    menuBtn.innerHTML = "☰";
    menuBtn.setAttribute("aria-label", "Menu");
    
    // Position it at the end
    topbar.appendChild(menuBtn);

    var overlay = document.querySelector(".mobile-menu-overlay");
    if (!overlay) {
        overlay = document.createElement("div");
        overlay.className = "mobile-menu-overlay";
        overlay.innerHTML = 
          '<button class="mobile-close-btn">&times;</button>' +
          '<nav class="mobile-nav-links">' +
          '<a href="index.html">Home</a>' +
          '<a href="films.html">Films</a>' +
          '<a href="other-projects.html">Other Projects</a>' +
          '<a href="cv.html">CV</a>' +
          '</nav>';
        document.body.appendChild(overlay);
    }

    var closeBtn = overlay.querySelector(".mobile-close-btn");

    menuBtn.addEventListener("click", function(e) {
      e.preventDefault();
      e.stopPropagation();
      overlay.classList.add("is-open");
    });
    
    if (closeBtn) {
        closeBtn.addEventListener("click", function() {
          overlay.classList.remove("is-open");
        });
    }
    
    overlay.querySelectorAll('a').forEach(function(link) {
        link.addEventListener('click', function() {
            overlay.classList.remove("is-open");
        });
    });
  }

  function wireExistingToggles() {
    var toggles = document.querySelectorAll("[data-lang-toggle]");
    toggles.forEach(function (toggle) {
      toggle.removeEventListener("click", handleToggle);
      toggle.addEventListener("click", handleToggle);
      toggle.textContent = LANG_LABEL;
    });
    return toggles.length > 0;
  }

  function init() {
    initMobileMenu();
    wireExistingToggles();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();