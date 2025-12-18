const scanButton = document.getElementById('scan-qr-btn');
const stopScanButton = document.getElementById('stop-scanning-btn');
const scannerContainer = document.getElementById('scanner-container');
const videoElement = document.getElementById('qr-video');

let videoStream;

// Event listener to start scanning when the button is clicked
scanButton.addEventListener('click', startScanner);
stopScanButton.addEventListener('click', stopScanner);

function startScanner() {
    scannerContainer.style.display = 'block';
    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
        .then(function(stream) {
            videoElement.srcObject = stream;
            videoStream = stream;
            videoElement.play();
            scanQRCode();
        })
        .catch(function(err) {
            console.error("Error accessing camera: ", err);
            alert("Failed to access camera.");
        });
}

function stopScanner() {
    if (videoStream) {
        let tracks = videoStream.getTracks();
        tracks.forEach(track => track.stop());
    }
    scannerContainer.style.display = 'none';
}

function scanQRCode() {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');

    function scan() {
        if (videoElement.readyState === videoElement.HAVE_ENOUGH_DATA) {
            canvas.height = videoElement.videoHeight;
            canvas.width = videoElement.videoWidth;
            context.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
            const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
            const code = jsQR(imageData.data, canvas.width, canvas.height, { inversionAttempts: "dontInvert" });

            if (code) {
                let qrCodeId = code.data;
                console.log('QR Code detected:', qrCodeId);

                // Extract UUID from URL or string
                const uuidPattern = /[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/i;
                
                // Try to parse as URL first
                try {
                    const urlObj = new URL(qrCodeId);
                    qrCodeId = urlObj.pathname.split('/').filter(Boolean).pop();
                } catch (e) {
                    // If URL parsing fails, try adding protocol
                    try {
                        const urlObj = new URL('https://' + qrCodeId);
                        qrCodeId = urlObj.pathname.split('/').filter(Boolean).pop();
                    } catch (e2) {
                        // If still fails, try to extract UUID directly from string
                        const uuidMatch = qrCodeId.match(uuidPattern);
                        if (uuidMatch) {
                            qrCodeId = uuidMatch[0];
                        } else {
                            // Try extracting from /scan/ pattern
                            if (qrCodeId.includes("/scan/")) {
                                qrCodeId = qrCodeId.split("/scan/").pop().split('/')[0];
                            } else {
                                // Remove leading/trailing slashes and whitespace
                                qrCodeId = qrCodeId.replace(/^\/+|\/+$/g, '').trim();
                            }
                        }
                    }
                }

                console.log('Extracted QR Code ID:', qrCodeId);

                // Validate UUID format
                const strictUuidPattern = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;
                if (!strictUuidPattern.test(qrCodeId)) {
                    console.error('Invalid UUID format:', qrCodeId);
                    showStatusOverlay('Invalid QR Code', 'error', 'red-x-icon.png');
                    return;
                }

                stopScanner();
                attendStudent(qrCodeId);
            }
        }
        requestAnimationFrame(scan);
    }

    scan();
}

function attendStudent(qrCodeId) {
    showLoadingSpinner();
    fetch(`/scan/${qrCodeId}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
        },
        body: JSON.stringify({ qr_code_id: qrCodeId }),
    })
        .then(response => response.json().then(data => ({ status: response.status, body: data })))
        .then(({ status, body }) => {
            hideLoadingSpinner();

            if (status === 200) {
                showStatusOverlay('Attendance marked successfully!', 'success', 'green-check-icon.png');
            } else if (status === 409) {
                showStatusOverlay(body.message, 'warning', 'yellow-exclamation-icon.png');
            } else if (status === 400) {
                showStatusOverlay(body.message, 'error', 'red-x-icon.png');
            } else {
                alert('An unexpected error occurred.');
            }
        })
        .catch(error => {
            hideLoadingSpinner();
            console.error('Error:', error);
            showStatusOverlay('Failed to mark attendance. Please try again.', 'error', 'red-x-icon.png');
        });
}

function showStatusMessage(message, type, icon) {
    const statusDiv = document.createElement('div');
    statusDiv.className = `status-message status-${type}`;
    statusDiv.innerHTML = `<img src="/static/assets/images/scan/${icon}" alt="${type}"> ${message}`;
    document.body.appendChild(statusDiv);
    statusDiv.style.display = 'flex';
    setTimeout(() => {
        statusDiv.remove();
    }, 3000);
}

function showLoadingSpinner() {
    scanButton.disabled = true;
    stopScanButton.disabled = true;
    const spinner = document.createElement('div');
    spinner.className = 'spinner';
    spinner.innerHTML = '<div class="loading"></div>';
    document.body.appendChild(spinner);
}

function hideLoadingSpinner() {
    scanButton.disabled = false;
    stopScanButton.disabled = false;
    document.querySelector('.spinner')?.remove();
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}


function showStatusOverlay(message, type, icon) {
    // Remove existing overlays (if any) to avoid duplication
    const existingOverlay = document.getElementById('status-overlay-container');
    if (existingOverlay) existingOverlay.remove();

    // Create the overlay container
    const overlayContainer = document.createElement('div');
    overlayContainer.id = 'status-overlay-container';

    // Create the status icon and message
    const iconElement = document.createElement('img');
    iconElement.src = `/static/assets/images/scan/${icon}`;
    iconElement.alt = `${type}`;
    iconElement.className = 'status-overlay'; // Optional class for additional styling

    // Append the icon to the container
    overlayContainer.appendChild(iconElement);

    // Append the container to the scanner container
    const scannerContainer = document.getElementById('scanner-container');
    scannerContainer.appendChild(overlayContainer);

    // Auto-remove the overlay after 3 seconds
    setTimeout(() => {
        overlayContainer.remove();
    }, 3000);
}
