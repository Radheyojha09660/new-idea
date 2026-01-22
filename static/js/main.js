// Main JavaScript for Video Library

document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(form);
            const fileInput = form.querySelector('input[type="file"]');
            const urlInput = form.querySelector('input[type="url"]');
            let endpoint = '/add_video';
            let message = 'Video processing started! It will appear in the folder once downloaded.';
            if (fileInput && fileInput.files.length > 0) {
                endpoint = '/upload_video';
                message = 'Video uploaded successfully!';
                // Remove url if file is selected
                if (urlInput) urlInput.value = '';
            } else if (!urlInput || !urlInput.value.trim()) {
                alert('Please enter a YouTube URL or select a video file.');
                return;
            }
            fetch(endpoint, {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                alert(message);
                form.reset();
            })
            .catch(error => {
                alert('Error: ' + error.message);
            });
        });
    }
});