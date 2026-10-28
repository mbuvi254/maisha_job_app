(() => {
  const button = document.getElementById('share-job');
  if (!button) return;
  button.addEventListener('click', async () => {
    const status = document.getElementById('share-status');
    const input = document.getElementById('job-link');
    try {
      await navigator.clipboard.writeText(input.value);
      status.textContent = 'Job link copied — ready to share.';
    } catch {
      document.getElementById('share-fallback').hidden = false;
      input.focus();
      input.select();
      status.textContent = 'Select and copy the job link below.';
    }
  });
})();
