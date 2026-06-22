document.addEventListener('DOMContentLoaded', function () {
    initTestimonialSlider();
    initSmoothScroll();
    initHeroComparison();
});

function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
        anchor.addEventListener('click', function (e) {
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });
}

function initTestimonialSlider() {
    const track = document.querySelector('.testimonial-track');
    const slides = document.querySelectorAll('.testimonial-slide');
    const prevBtn = document.getElementById('prevTestimonial');
    const nextBtn = document.getElementById('nextTestimonial');

    if (!track || slides.length <= 1) return;

    let current = 0;

    function goTo(index) {
        current = (index + slides.length) % slides.length;
        track.style.transform = 'translateX(-' + (current * 100) + '%)';
    }

    if (prevBtn) prevBtn.addEventListener('click', function () { goTo(current - 1); });
    if (nextBtn) nextBtn.addEventListener('click', function () { goTo(current + 1); });

    setInterval(function () { goTo(current + 1); }, 6000);
}

function initHeroComparison() {
    const container = document.getElementById('heroComparison');
    const cleanWrap = document.getElementById('heroComparisonClean');
    const handle = document.getElementById('heroComparisonHandle');
    if (!container || !cleanWrap || !handle) return;

    const cleanImg = cleanWrap.querySelector('img');
    let split = parseFloat(container.dataset.split) || 50;
    let dragging = false;

    function clamp(value) {
        return Math.min(Math.max(value, 5), 95);
    }

    function syncImageWidth() {
        if (!cleanImg) return;
        cleanImg.style.width = container.offsetWidth + 'px';
    }

    function setSplit(percent) {
        split = clamp(percent);
        container.dataset.split = split;
        cleanWrap.style.width = split + '%';
        handle.style.left = split + '%';
    }

    function splitFromEvent(clientX) {
        const rect = container.getBoundingClientRect();
        return ((clientX - rect.left) / rect.width) * 100;
    }

    function onPointerDown(e) {
        dragging = true;
        container.classList.add('is-dragging');
        setSplit(splitFromEvent(e.clientX));
        container.setPointerCapture(e.pointerId);
    }

    function onPointerMove(e) {
        if (!dragging) return;
        setSplit(splitFromEvent(e.clientX));
    }

    function onPointerUp(e) {
        dragging = false;
        container.classList.remove('is-dragging');
        try { container.releasePointerCapture(e.pointerId); } catch (_) {}
    }

    function onWheel(e) {
        if (!container.matches(':hover')) return;
        e.preventDefault();
        const delta = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
        setSplit(split + delta * 0.08);
    }

    container.addEventListener('pointerdown', onPointerDown);
    container.addEventListener('pointermove', onPointerMove);
    container.addEventListener('pointerup', onPointerUp);
    container.addEventListener('pointercancel', onPointerUp);
    container.addEventListener('wheel', onWheel, { passive: false });

    window.addEventListener('resize', function () {
        syncImageWidth();
        setSplit(split);
    });

    if (cleanImg.complete) {
        syncImageWidth();
        setSplit(split);
    } else {
        cleanImg.addEventListener('load', function () {
            syncImageWidth();
            setSplit(split);
        });
    }
}
