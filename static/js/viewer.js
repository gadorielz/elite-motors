/**
 * Elite Motors — 360° Drag-to-Spin Viewer
 * Canvas-based, no external deps.
 * Expects global PHOTOS array and #viewer360 canvas.
 */
(function () {
  const canvas = document.getElementById('viewer360');
  if (!canvas || !window.PHOTOS || PHOTOS.length < 2) return;

  const ctx = canvas.getContext('2d');
  const hint = document.querySelector('.viewer-hint');
  const thumbs = document.querySelectorAll('#thumbStrip .thumb');

  let images = [];
  let loaded = 0;
  let currentIndex = 0;
  let isDragging = false;
  let startX = 0;
  let lastX = 0;
  let scale = 1;
  let minScale = 1;
  let maxScale = 4;
  let offsetX = 0;
  let offsetY = 0;
  let pinchDist = null;
  let lastTouchX = 0;

  // Sensitivity: pixels to drag for one frame advance
  const DRAG_SENSITIVITY = 28;
  let dragAccumulator = 0;

  // ──────────────────────────────────────────────────────────
  // Load all images
  // ──────────────────────────────────────────────────────────
  function loadImages() {
    PHOTOS.forEach((src, i) => {
      const img = new Image();
      img.onload = () => {
        images[i] = img;
        loaded++;
        if (loaded === 1) {
          // Draw first image as soon as it's ready
          fitCanvas(img);
          drawFrame(0);
        }
        if (loaded === PHOTOS.length) {
          drawFrame(currentIndex);
        }
      };
      img.onerror = () => { loaded++; };
      img.src = src;
    });
  }

  function fitCanvas(img) {
    // Keep canvas 16:10 ratio, responsive
    const w = canvas.parentElement.clientWidth || 800;
    canvas.width = w;
    canvas.height = Math.round(w * (10 / 16));
  }

  // ──────────────────────────────────────────────────────────
  // Draw
  // ──────────────────────────────────────────────────────────
  function drawFrame(index) {
    index = ((index % PHOTOS.length) + PHOTOS.length) % PHOTOS.length;
    currentIndex = index;

    const img = images[index];
    if (!img) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();

    const cw = canvas.width;
    const ch = canvas.height;

    // Compute natural fit (contain)
    const naturalScale = Math.min(cw / img.naturalWidth, ch / img.naturalHeight);
    const drawW = img.naturalWidth * naturalScale * scale;
    const drawH = img.naturalHeight * naturalScale * scale;

    // Center + offset
    const x = (cw - drawW) / 2 + offsetX;
    const y = (ch - drawH) / 2 + offsetY;

    ctx.drawImage(img, x, y, drawW, drawH);
    ctx.restore();

    // Update thumbnail highlight
    thumbs.forEach((t, i) => t.classList.toggle('active', i === index));
  }

  // ──────────────────────────────────────────────────────────
  // Mouse events
  // ──────────────────────────────────────────────────────────
  canvas.addEventListener('mousedown', (e) => {
    isDragging = true;
    startX = e.clientX;
    lastX = e.clientX;
    dragAccumulator = 0;
    canvas.style.cursor = 'grabbing';
    if (hint) hint.style.opacity = '0';
  });

  window.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const dx = e.clientX - lastX;
    lastX = e.clientX;
    dragAccumulator += dx;

    if (Math.abs(dragAccumulator) >= DRAG_SENSITIVITY) {
      const steps = Math.round(dragAccumulator / DRAG_SENSITIVITY);
      drawFrame(currentIndex - steps);
      dragAccumulator = dragAccumulator % DRAG_SENSITIVITY;
    }
  });

  window.addEventListener('mouseup', () => {
    isDragging = false;
    canvas.style.cursor = 'grab';
  });

  // Scroll to zoom
  canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const delta = e.deltaY < 0 ? 0.1 : -0.1;
    scale = Math.min(maxScale, Math.max(minScale, scale + delta));
    drawFrame(currentIndex);
  }, { passive: false });

  // ──────────────────────────────────────────────────────────
  // Touch events
  // ──────────────────────────────────────────────────────────
  canvas.addEventListener('touchstart', (e) => {
    if (e.touches.length === 1) {
      isDragging = true;
      lastTouchX = e.touches[0].clientX;
      dragAccumulator = 0;
      if (hint) hint.style.opacity = '0';
    } else if (e.touches.length === 2) {
      isDragging = false;
      pinchDist = getPinchDist(e.touches);
    }
  }, { passive: true });

  canvas.addEventListener('touchmove', (e) => {
    e.preventDefault();
    if (e.touches.length === 1 && isDragging) {
      const dx = e.touches[0].clientX - lastTouchX;
      lastTouchX = e.touches[0].clientX;
      dragAccumulator += dx;
      if (Math.abs(dragAccumulator) >= DRAG_SENSITIVITY) {
        const steps = Math.round(dragAccumulator / DRAG_SENSITIVITY);
        drawFrame(currentIndex - steps);
        dragAccumulator = dragAccumulator % DRAG_SENSITIVITY;
      }
    } else if (e.touches.length === 2 && pinchDist !== null) {
      const newDist = getPinchDist(e.touches);
      const ratio = newDist / pinchDist;
      scale = Math.min(maxScale, Math.max(minScale, scale * ratio));
      pinchDist = newDist;
      drawFrame(currentIndex);
    }
  }, { passive: false });

  canvas.addEventListener('touchend', () => {
    isDragging = false;
    pinchDist = null;
  });

  function getPinchDist(touches) {
    const dx = touches[0].clientX - touches[1].clientX;
    const dy = touches[0].clientY - touches[1].clientY;
    return Math.hypot(dx, dy);
  }

  // ──────────────────────────────────────────────────────────
  // Thumbnail click
  // ──────────────────────────────────────────────────────────
  thumbs.forEach((thumb, i) => {
    thumb.addEventListener('click', () => {
      drawFrame(i);
    });
  });

  // ──────────────────────────────────────────────────────────
  // Auto-spin on load (brief 360 teaser)
  // ──────────────────────────────────────────────────────────
  function autoSpin() {
    let frame = 0;
    const total = PHOTOS.length;
    const interval = setInterval(() => {
      drawFrame(frame % total);
      frame++;
      if (frame >= total) clearInterval(interval);
    }, 80);
  }

  // ──────────────────────────────────────────────────────────
  // Responsive resize
  // ──────────────────────────────────────────────────────────
  window.addEventListener('resize', () => {
    if (images[currentIndex]) {
      fitCanvas(images[currentIndex]);
      drawFrame(currentIndex);
    }
  });

  // ──────────────────────────────────────────────────────────
  // Init
  // ──────────────────────────────────────────────────────────
  loadImages();

  // Trigger auto spin after images load
  const spinCheck = setInterval(() => {
    if (loaded === PHOTOS.length) {
      clearInterval(spinCheck);
      setTimeout(autoSpin, 400);
    }
  }, 200);

})();
