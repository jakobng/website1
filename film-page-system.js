(function () {
  // Reveal animations
  var cards = document.querySelectorAll(".film-card");
  var observerOptions = { threshold: 0.1 };

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
      }
    });
  }, observerOptions);

  cards.forEach(function (card) {
    observer.observe(card);
  });

  // Mobile Menu Logic
  var topbar = document.querySelector(".film-topbar");
  if (topbar && !document.querySelector('.mobile-menu-btn')) {
    // 1. Create Menu Button
    var menuBtn = document.createElement("button");
    menuBtn.className = "mobile-menu-btn";
    menuBtn.innerHTML = "☰";
    menuBtn.setAttribute("aria-label", "Menu");
    topbar.appendChild(menuBtn);

    // 2. Create Overlay
    var overlay = document.createElement("div");
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

    var closeBtn = overlay.querySelector(".mobile-close-btn");

    menuBtn.addEventListener("click", function() {
      overlay.classList.add("is-open");
    });
    closeBtn.addEventListener("click", function() {
      overlay.classList.remove("is-open");
    });
    
    // Close on link click
    overlay.querySelectorAll('a').forEach(function(link) {
        link.addEventListener('click', function() {
            overlay.classList.remove("is-open");
        });
    });
  }
})();