// Main JavaScript file for FileNet application

// Initialize tooltips and popovers when the document is ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize all tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize all popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // File upload form validation
    const fileUploadForm = document.querySelector('form[enctype="multipart/form-data"]');
    if (fileUploadForm) {
        fileUploadForm.addEventListener('submit', function(event) {
            const fileInput = document.getElementById('file');
            
            if (fileInput && fileInput.files.length > 0) {
                const file = fileInput.files[0];
                const maxSize = 50 * 1024 * 1024; // 50MB
                
                if (file.size > maxSize) {
                    event.preventDefault();
                    alert('File size exceeds the maximum allowed (50MB)');
                }
            }
        });
    }

    // Preview uploaded file when selected
    const fileInput = document.getElementById('file');
    const previewContainer = document.getElementById('file-preview');
    
    if (fileInput && previewContainer) {
        fileInput.addEventListener('change', function() {
            if (this.files && this.files[0]) {
                const file = this.files[0];
                const fileType = file.type.split('/')[0];
                
                // Clear previous preview
                previewContainer.innerHTML = '';
                
                // Show file info
                const fileInfo = document.createElement('div');
                fileInfo.className = 'mb-3';
                fileInfo.innerHTML = `
                    <h6>Selected File</h6>
                    <p><strong>Name:</strong> ${file.name}</p>
                    <p><strong>Size:</strong> ${Math.round(file.size / 1024)} KB</p>
                    <p><strong>Type:</strong> ${file.type}</p>
                `;
                previewContainer.appendChild(fileInfo);
                
                // Show preview for image files
                if (fileType === 'image') {
                    const reader = new FileReader();
                    
                    reader.onload = function(e) {
                        const img = document.createElement('img');
                        img.src = e.target.result;
                        img.className = 'img-fluid';
                        img.alt = file.name;
                        
                        previewContainer.appendChild(img);
                    };
                    
                    reader.readAsDataURL(file);
                }
            }
        });
    }

    // Search functionality
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('keyup', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                document.getElementById('search-form').submit();
            }
        });
    }

    // File sharing modal functionality
    const sharingForm = document.getElementById('sharing-form');
    if (sharingForm) {
        const userCheckboxes = document.querySelectorAll('.user-permission');
        
        userCheckboxes.forEach(function(checkbox) {
            checkbox.addEventListener('change', function() {
                const userId = this.dataset.userId;
                const permType = this.dataset.permission;
                
                // If read permission is unchecked, uncheck write and delete too
                if (permType === 'read' && !this.checked) {
                    const writeCheck = document.querySelector(`[data-user-id="${userId}"][data-permission="write"]`);
                    const deleteCheck = document.querySelector(`[data-user-id="${userId}"][data-permission="delete"]`);
                    
                    if (writeCheck) writeCheck.checked = false;
                    if (deleteCheck) deleteCheck.checked = false;
                }
                
                // If write or delete is checked, ensure read is also checked
                if ((permType === 'write' || permType === 'delete') && this.checked) {
                    const readCheck = document.querySelector(`[data-user-id="${userId}"][data-permission="read"]`);
                    
                    if (readCheck) readCheck.checked = true;
                }
            });
        });
    }
});
