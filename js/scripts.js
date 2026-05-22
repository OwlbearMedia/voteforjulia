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

if (contactForm) {
  contactForm.addEventListener('submit', function(event) {
    const emailInput = document.getElementById('contact-email');
    const email = emailInput.value;
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (!emailRegex.test(email)) {
      event.preventDefault();
      alert('Please enter a valid email address.');
      emailInput.focus();
    }
  });
}