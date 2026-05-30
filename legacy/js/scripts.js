const header = document.querySelector('header');
const contactForms = document.querySelectorAll('.contact-form');

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

contactForms.forEach(function(contactForm) {
  contactForm.addEventListener('submit', async function(event) {
    event.preventDefault();

    const emailInput = contactForm.querySelector('#contact-email');
    const nameInput = contactForm.querySelector('#contact-name');
    const phoneInput = contactForm.querySelector('#contact-phone');
    const messageInput = contactForm.querySelector('#contact-message');
    const checkedHelpWays = Array.from(contactForm.querySelectorAll('input[name="helpWays[]"]:checked'));
    const email = (emailInput ? emailInput.value : '').trim();
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (!emailRegex.test(email)) {
      alert('Please enter a valid email address.');
      if (emailInput) {
        emailInput.focus();
      }
      return;
    }

    const payload = {
      name: nameInput ? nameInput.value.trim() : '',
      email: email,
      phone: phoneInput ? phoneInput.value.trim() : '',
      message: messageInput ? messageInput.value.trim() : '',
      helpWays: checkedHelpWays.map(function(input) {
        return input.value.trim();
      })
    };

    const submitButton = contactForm.querySelector('button[type="submit"]');
    if (submitButton) {
      submitButton.disabled = true;
    }

    try {
      const response = await fetch(contactForm.action, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      const result = await response.json().catch(function() {
        return {};
      });

      if (!response.ok) {
        throw new Error(result.error || 'Unable to submit your form right now.');
      }

      trackGaEvent('volunteer_form_submit', {
        form_id: contactForm.id || 'contact-form',
        form_location: window.location.pathname,
        submission_status: 'success'
      });

      alert('Thanks for reaching out. We received your submission.');
      contactForm.reset();
    } catch (error) {
      trackGaEvent('volunteer_form_submit', {
        form_id: contactForm.id || 'contact-form',
        form_location: window.location.pathname,
        submission_status: 'error'
      });

      alert(error.message || 'Unable to submit your form right now.');
    } finally {
      if (submitButton) {
        submitButton.disabled = false;
      }
    }
  });
});