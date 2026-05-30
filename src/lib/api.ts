export async function submitContactForm(
  formData: Record<string, string>,
): Promise<void> {
  try {
    const response = await fetch("https://api.voteforjulia.com/send-email", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(formData),
    });

    if (!response.ok) {
      let message = "Unable to send your message right now. Please try again.";

      try {
        const payload = await response.json();
        if (typeof payload?.error === "string" && payload.error.trim()) {
          message = payload.error;
        }
      } catch {
        // Keep default message when response body is not valid JSON.
      }

      throw new Error(message);
    }
  } catch (error) {
    console.error("Error submitting contact form:", error);
    throw error;
  }
}
