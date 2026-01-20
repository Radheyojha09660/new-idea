// Study Portal Main Script

document.addEventListener('DOMContentLoaded', function() {
    console.log('Study Portal loaded');

    // Add any dashboard interactivity here
    const startButtons = document.querySelectorAll('.start-btn');
    startButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            if (!confirm('Are you ready to start the test? Timer will begin immediately.')) {
                e.preventDefault();
            }
        });
    });
});