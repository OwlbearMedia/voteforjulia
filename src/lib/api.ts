const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, '') ||
  'https://api.voteforjulia.com';

export async function submitContactForm(formData: Record<string, string>): Promise<void> {
  try {
    const response = await fetch(`${API_BASE_URL}/send-email`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(formData)
    });

    if (!response.ok) {
      let message = 'Unable to send your message right now. Please try again.';

      try {
        const payload = await response.json();
        if (typeof payload?.error === 'string' && payload.error.trim()) {
          message = payload.error;
        }
      } catch {
        // Keep default message when response body is not valid JSON.
      }

      throw new Error(message);
    }
  } catch (error) {
    console.error('Error submitting contact form:', error);
    throw error;
  }
}
