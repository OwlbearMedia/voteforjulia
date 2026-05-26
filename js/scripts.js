// Hamburger menu toggle
const menuToggle = document.querySelector('.menu-toggle');
const menuList = document.getElementById('main-menu');

if (menuToggle && menuList) {
  menuToggle.addEventListener('click', function() {
    const isOpen = menuList.classList.toggle('open');
    menuToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  });

  menuList.querySelectorAll('a').forEach(function(link) {
    link.addEventListener('click', function() {
      menuList.classList.remove('open');
      menuToggle.setAttribute('aria-expanded', 'false');
    });
  });
}

const header = document.querySelector('header');
const contactForm = document.querySelector('.contact-form');

function trackGaEvent(eventName, params) {
  if (typeof window.gtag !== 'function') {
    return;
  }

  window.gtag('event', eventName, {
    ...params,
    transport_type: 'beacon'
  });
}

function normalizeFooterIconLabel(link) {
  const href = (link.getAttribute('href') || '').toLowerCase();
  const ariaLabel = (link.getAttribute('aria-label') || '').toLowerCase();

  if (href.startsWith('mailto:') || ariaLabel.includes('email')) {
    return 'email';
  }

  if (ariaLabel.includes('instagram') || href.includes('instagram.com')) {
    return 'instagram';
  }

  if (ariaLabel.includes('facebook') || href.includes('facebook.com')) {
    return 'facebook';
  }

  return 'other';
}

function updateHeaderOffset() {
  if (!header) {
    return;
  }

  const headerHeight = header.offsetHeight;
  document.documentElement.style.setProperty('--header-height', `${headerHeight}px`);
}

updateHeaderOffset();
window.addEventListener('load', updateHeaderOffset);
window.addEventListener('resize', updateHeaderOffset);

document.querySelectorAll('a[href*="/donate.html"]').forEach(function(link) {
  link.addEventListener('click', function() {
    const section = link.closest('header, footer, main, section');
    const linkLocation = section ? section.tagName.toLowerCase() : 'unknown';

    trackGaEvent('donate_click', {
      link_location: linkLocation,
      link_text: (link.textContent || '').trim() || 'donate'
    });
  });
});

document.querySelectorAll('footer .social-icons a').forEach(function(link) {
  link.addEventListener('click', function() {
    trackGaEvent('footer_icon_click', {
      icon_label: normalizeFooterIconLabel(link),
      icon_label_raw: link.getAttribute('aria-label') || 'unknown',
      link_url: link.getAttribute('href') || '',
      link_type: (link.getAttribute('href') || '').startsWith('mailto:') ? 'email' : 'social'
    });
  });
});

if (contactForm) {
  contactForm.addEventListener('submit', function(event) {
    const emailInput = document.getElementById('contact-email');
    const email = emailInput.value;
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (!emailRegex.test(email)) {
      event.preventDefault();
      alert('Please enter a valid email address.');
      emailInput.focus();
      return;
    }

    trackGaEvent('volunteer_form_submit', {
      form_id: contactForm.id || 'contact-form',
      form_location: window.location.pathname
    });
  });
}