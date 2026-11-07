(function () {
  'use strict';

  var MAX_CAPTURE_EDGE = 1920;
  var JPEG_QUALITY = 0.92;

  function pad(value) {
    return value < 10 ? '0' + value : '' + value;
  }

  function photoName(date) {
    return 'camera-photo-'
      + date.getFullYear() + pad(date.getMonth() + 1) + pad(date.getDate())
      + '-'
      + pad(date.getHours()) + pad(date.getMinutes()) + pad(date.getSeconds())
      + '.jpg';
  }

  function create(button, attachments, options) {
    if (!button || !attachments || typeof attachments.addFiles !== 'function') {
      return null;
    }
    options = options || {};

    var modal = document.querySelector('[data-camera-modal]');
    var fallbackInput = document.querySelector('[data-camera-file]');
    if (!modal || !fallbackInput) return null;

    var video = modal.querySelector('[data-camera-video]');
    var photo = modal.querySelector('[data-camera-photo]');
    var canvas = modal.querySelector('[data-camera-canvas]');
    var loading = modal.querySelector('[data-camera-loading]');
    var message = modal.querySelector('[data-camera-message]');
    var controls = modal.querySelector('[data-camera-controls]');
    var review = modal.querySelector('[data-camera-review]');
    var shutter = modal.querySelector('[data-camera-shutter]');
    var switchButton = modal.querySelector('[data-camera-switch]');
    var fallbackButton = modal.querySelector('[data-camera-fallback]');
    var useButton = modal.querySelector('[data-camera-use]');
    var retakeButton = modal.querySelector('[data-camera-retake]');
    var closeButtons = modal.querySelectorAll('[data-camera-close]');

    if (!video || !photo || !canvas || !loading || !message
        || !controls || !review || !shutter) {
      return null;
    }

    var stream = null;
    var facing = 'environment';
    var capturedFile = null;
    var capturedUrl = '';
    var starting = false;
    var lastFocus = null;
    var hasCamera = !!(navigator.mediaDevices
      && navigator.mediaDevices.getUserMedia);

    function notify(text) {
      if (typeof options.onStatus === 'function') options.onStatus(text || '');
    }

    function setMessage(text) {
      message.textContent = text || '';
      message.hidden = !text;
    }

    function setLoading(active, label) {
      loading.hidden = !active;
      var copy = loading.querySelector('span');
      if (copy && label) copy.textContent = label;
    }

    function setBusy(busy) {
      shutter.disabled = !!busy || !stream;
      if (switchButton) switchButton.disabled = !!busy || !stream;
    }

    function stopStream() {
      if (stream) {
        try {
          stream.getTracks().forEach(function (track) { track.stop(); });
        } catch (error) {}
      }
      stream = null;
      video.srcObject = null;
    }

    function releaseCapture() {
      if (capturedUrl) {
        URL.revokeObjectURL(capturedUrl);
        capturedUrl = '';
      }
      capturedFile = null;
      photo.removeAttribute('src');
      photo.hidden = true;
      video.hidden = false;
      review.hidden = true;
      controls.hidden = false;
      shutter.hidden = false;
      if (switchButton) switchButton.hidden = false;
    }

    function reset() {
      stopStream();
      releaseCapture();
      setMessage('');
      setLoading(false);
      setBusy(false);
    }

    function showError(error) {
      var name = error && error.name ? error.name : '';
      var text;
      if (name === 'NotAllowedError' || name === 'SecurityError') {
        text = 'Camera access was denied. Allow camera access in your browser settings, or upload a photo instead.';
      } else if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
        text = 'No camera was found on this device. You can upload a photo instead.';
      } else if (name === 'NotReadableError' || name === 'TrackStartError') {
        text = 'The camera is busy in another app. Close it and try again, or upload a photo instead.';
      } else {
        text = 'The camera could not start. Upload a photo instead.';
      }
      setLoading(false);
      setBusy(false);
      video.hidden = true;
      shutter.hidden = true;
      if (switchButton) switchButton.hidden = true;
      setMessage(text);
    }

    function handleStream(nextStream, nextFacing) {
      stopStream();
      stream = nextStream;
      facing = nextFacing;
      video.srcObject = stream;
      video.hidden = false;
      photo.hidden = true;
      review.hidden = true;
      controls.hidden = false;
      shutter.hidden = false;
      if (switchButton) switchButton.hidden = false;
      setLoading(false);
      setMessage('');
      setBusy(false);
      if (!modal.hidden) shutter.focus();

      var playPromise = video.play();
      if (playPromise && typeof playPromise.catch === 'function') {
        playPromise.catch(function () {
          setMessage('Tap the camera preview to start it.');
        });
      }
    }

    function requestStream(nextFacing) {
      var constraints = {
        audio: false,
        video: {
          facingMode: { ideal: nextFacing },
          width: { ideal: 1920 },
          height: { ideal: 1440 }
        }
      };
      return navigator.mediaDevices.getUserMedia(constraints).catch(function (error) {
        var name = error && error.name ? error.name : '';
        if (name === 'OverconstrainedError'
            || name === 'ConstraintNotSatisfiedError'
            || name === 'TypeError') {
          return navigator.mediaDevices.getUserMedia({ audio: false, video: true });
        }
        throw error;
      });
    }

    function openFilePicker() {
      fallbackInput.value = '';
      fallbackInput.click();
    }

    function startCamera(nextFacing) {
      if (starting || capturedFile) return;
      if (!hasCamera) {
        setLoading(false);
        setBusy(false);
        video.hidden = true;
        shutter.hidden = true;
        if (switchButton) switchButton.hidden = true;
        setMessage('Camera capture is not supported by this browser. Choose a photo instead.');
        openFilePicker();
        return;
      }

      starting = true;
      stopStream();
      setMessage('');
      setLoading(true, nextFacing === facing ? 'Starting camera…' : 'Switching camera…');
      setBusy(true);

      requestStream(nextFacing).then(function (nextStream) {
        starting = false;
        handleStream(nextStream, nextFacing);
      }).catch(function (error) {
        starting = false;
        showError(error);
      });
    }

    function open() {
      lastFocus = document.activeElement;
      modal.hidden = false;
      document.body.classList.add('camera-open');
      releaseCapture();
      setMessage('');
      setBusy(true);
      if (hasCamera) {
        window.setTimeout(function () {
          if (!modal.hidden && !shutter.hidden && !shutter.disabled) {
            shutter.focus();
          }
        }, 40);
      }
      startCamera(facing);
    }

    function close() {
      modal.hidden = true;
      document.body.classList.remove('camera-open');
      reset();
      if (lastFocus && typeof lastFocus.focus === 'function') {
        lastFocus.focus();
      }
      lastFocus = null;
    }

    function capture() {
      if (!stream || !video.videoWidth || !video.videoHeight) return;
      if (typeof canvas.toBlob !== 'function') {
        setMessage('This browser cannot save photos. Upload a photo instead.');
        return;
      }

      var scale = Math.min(
        MAX_CAPTURE_EDGE / Math.max(video.videoWidth, video.videoHeight),
        1
      );
      canvas.width = Math.round(video.videoWidth * scale);
      canvas.height = Math.round(video.videoHeight * scale);

      var context = canvas.getContext('2d');
      if (!context) {
        setMessage('This browser cannot capture photos. Upload a photo instead.');
        return;
      }
      context.drawImage(video, 0, 0, canvas.width, canvas.height);

      setBusy(true);
      setLoading(true, 'Saving photo…');
      canvas.toBlob(function (blob) {
        setLoading(false);
        if (!blob) {
          setBusy(false);
          setMessage('The photo could not be saved. Please try again.');
          return;
        }

        stopStream();
        if (capturedUrl) URL.revokeObjectURL(capturedUrl);
        capturedUrl = URL.createObjectURL(blob);
        capturedFile = new File([blob], photoName(new Date()), {
          type: 'image/jpeg',
          lastModified: Date.now()
        });

        photo.src = capturedUrl;
        photo.hidden = false;
        video.hidden = true;
        shutter.hidden = true;
        if (switchButton) switchButton.hidden = true;
        controls.hidden = true;
        review.hidden = false;
        setMessage('');
        if (useButton) useButton.focus();
      }, 'image/jpeg', JPEG_QUALITY);
    }

    function usePhoto() {
      if (!capturedFile) return;
      var added = attachments.addFiles([capturedFile]);
      if (added === false) {
        setMessage('The photo could not be added. Check the attachment limits and try again.');
        return;
      }
      notify('Photo added to your message.');
      close();
    }

    function retake() {
      releaseCapture();
      setMessage('');
      startCamera(facing);
    }

    button.addEventListener('click', open);
    shutter.addEventListener('click', capture);
    if (useButton) useButton.addEventListener('click', usePhoto);
    if (retakeButton) retakeButton.addEventListener('click', retake);
    if (fallbackButton) fallbackButton.addEventListener('click', openFilePicker);
    if (switchButton) {
      switchButton.addEventListener('click', function () {
        startCamera(facing === 'environment' ? 'user' : 'environment');
      });
    }

    for (var index = 0; index < closeButtons.length; index += 1) {
      closeButtons[index].addEventListener('click', close);
    }

    fallbackInput.addEventListener('change', function () {
      var files = fallbackInput.files;
      if (files && files.length) {
        var added = attachments.addFiles(files);
        if (added === false) {
          if (!modal.hidden) {
            setMessage('The photo could not be added. Check the attachment limits and try again.');
          }
        } else {
          notify('Photo added to your message.');
          if (!modal.hidden) close();
        }
      }
      fallbackInput.value = '';
    });

    document.addEventListener('keydown', function (event) {
      if (modal.hidden) return;

      if (event.key === 'Escape') {
        event.preventDefault();
        close();
        return;
      }

      if (event.key !== 'Tab') return;
      var focusable = modal.querySelectorAll(
        'button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'
      );
      var visible = [];
      for (var item = 0; item < focusable.length; item += 1) {
        if (focusable[item].offsetParent !== null) visible.push(focusable[item]);
      }
      if (!visible.length) return;

      var first = visible[0];
      var last = visible[visible.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });

    window.addEventListener('pagehide', stopStream);

    return {
      open: open,
      close: close
    };
  }

  window.TechFixCamera = {
    create: create
  };
})();
