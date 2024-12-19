// تحديث العد التنازلي
function updateCountdowns() {
    document.querySelectorAll('.countdown-text').forEach(countdown => {
        const deadline = new Date(countdown.dataset.deadline);
        const now = new Date();
        const diff = deadline - now;
        const totalDuration = deadline - new Date(countdown.dataset.deadline);

        if (diff > 0) {
            const days = Math.floor(diff / (1000 * 60 * 60 * 24));
            const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((diff % (1000 * 60)) / 1000);

            let timeString = 'الوقت المتبقي: ';
            if (days > 0) timeString += `${days} يوم `;
            if (hours > 0) timeString += `${hours} ساعة `;
            if (minutes > 0) timeString += `${minutes} دقيقة `;
            timeString += `${seconds} ثانية`;

            countdown.querySelector('.countdown-value').textContent = timeString;

            // تحديث شريط التقدم
            const progressBar = countdown.nextElementSibling.querySelector('.progress-bar');
            const percentageLeft = (diff / (24 * 60 * 60 * 1000)) * 100; // النسبة المئوية المتبقية من اليوم
            progressBar.style.width = `${percentageLeft}%`;

            // إضافة تنسيق التحذير عند اقتراب الموعد النهائي
            if (diff <= 24 * 60 * 60 * 1000) { // أقل من يوم
                countdown.classList.add('warning');
                progressBar.classList.add('warning');
            } else {
                countdown.classList.remove('warning');
                progressBar.classList.remove('warning');
            }
        } else {
            countdown.querySelector('.countdown-value').textContent = 'انتهت المهلة';
            countdown.classList.add('warning');
            const progressBar = countdown.nextElementSibling.querySelector('.progress-bar');
            progressBar.style.width = '0%';
            progressBar.classList.add('warning');
        }
    });
}

// تحديث العد التنازلي كل ثانية
setInterval(updateCountdowns, 1000);
updateCountdowns();

// التعامل مع الملفات المرفقة
document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('attachments');
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const files = Array.from(e.target.files);
            const previewContainer = document.createElement('div');
            previewContainer.className = 'attachment-preview';
            
            files.forEach(file => {
                if (file.type.startsWith('image/')) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        const img = document.createElement('img');
                        img.src = e.target.result;
                        img.className = 'mb-2 me-2';
                        previewContainer.appendChild(img);
                    }
                    reader.readAsDataURL(file);
                }
            });
            
            const existingPreview = fileInput.parentElement.querySelector('.attachment-preview');
            if (existingPreview) {
                existingPreview.remove();
            }
            fileInput.parentElement.appendChild(previewContainer);
        });
    }
});

// دالة إدارة الكاميرا
function initializeCamera() {
    const videoElement = document.querySelector('video');
    if (videoElement) {
        // إضافة الفئات للتنسيق
        videoElement.classList.add('camera-video');
        const container = document.createElement('div');
        container.className = 'camera-container';
        videoElement.parentElement.insertBefore(container, videoElement);
        container.appendChild(videoElement);

        // إنشاء زر الإغلاق
        const closeButton = document.createElement('button');
        closeButton.className = 'camera-close-btn btn';
        closeButton.innerHTML = '<i class="fas fa-times"></i> إغلاق الكاميرا';
        
        // وظيفة إغلاق الكاميرا
        closeButton.onclick = function() {
            if (videoElement.srcObject) {
                const tracks = videoElement.srcObject.getTracks();
                tracks.forEach(track => {
                    track.stop();
                    videoElement.srcObject.removeTrack(track);
                });
                videoElement.srcObject = null;
                container.style.display = 'none';
            }
        };

        container.appendChild(closeButton);

        // معالجة أخطاء الكاميرا
        videoElement.onerror = function(error) {
            console.error('خطأ في الكاميرا:', error);
            alert('حدث خطأ في الوصول إلى الكاميرا. يرجى التحقق من إذونات الكاميرا.');
        };
    }
}

// تهيئة الكاميرا عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', function() {
    initializeCamera();
    
    // إعادة تهيئة الكاميرا عند فتحها من جديد
    const cameraButtons = document.querySelectorAll('.open-camera-btn');
    cameraButtons.forEach(button => {
        button.addEventListener('click', function() {
            const container = document.querySelector('.camera-container');
            if (container) {
                container.style.display = 'block';
                initializeCamera();
            }
        });
    });

    const captureBtn = document.getElementById('capture-photo');
    const videoPreview = document.getElementById('camera-preview');
    const photoCanvas = document.getElementById('photo-canvas');
    let stream = null;

    if (captureBtn) {
        captureBtn.addEventListener('click', async function() {
            try {
                if (videoPreview.style.display === 'none') {
                    stream = await navigator.mediaDevices.getUserMedia({ 
                        video: { 
                            facingMode: 'environment',
                            width: { ideal: 1280 },
                            height: { ideal: 720 }
                        } 
                    });
                    videoPreview.srcObject = stream;
                    videoPreview.style.display = 'block';
                    captureBtn.innerHTML = '<i class="fas fa-camera"></i> التقاط الصورة';
                } else {
                    // التقاط الصورة
                    photoCanvas.width = videoPreview.videoWidth;
                    photoCanvas.height = videoPreview.videoHeight;
                    const context = photoCanvas.getContext('2d');
                    context.drawImage(videoPreview, 0, 0);
                    
                    // تحويل الصورة إلى ملف
                    photoCanvas.toBlob(function(blob) {
                        const file = new File([blob], `camera-${new Date().getTime()}.jpg`, { type: 'image/jpeg' });
                        
                        // إضافة الصورة إلى input الملفات
                        const dataTransfer = new DataTransfer();
                        const fileInput = document.getElementById('attachments');
                        
                        // إضافة الملفات الموجودة مسبقاً
                        if (fileInput.files.length) {
                            Array.from(fileInput.files).forEach(existingFile => {
                                dataTransfer.items.add(existingFile);
                            });
                        }
                        
                        // إضافة الصورة الجديدة
                        dataTransfer.items.add(file);
                        fileInput.files = dataTransfer.files;
                        
                        // عرض معاينة الصورة
                        const event = new Event('change');
                        fileInput.dispatchEvent(event);
                    }, 'image/jpeg', 0.8);

                    // إيقاف الكاميرا
                    stream.getTracks().forEach(track => track.stop());
                    videoPreview.style.display = 'none';
                    captureBtn.innerHTML = '<i class="fas fa-camera"></i> تشغيل الكاميرا';
                }
            } catch (err) {
                console.error('خطأ في الوصول إلى الكاميرا:', err);
                alert('لا يمكن الوصول إلى الكاميرا. يرجى التحقق من الإذن.');
            }
        });
    }
});
