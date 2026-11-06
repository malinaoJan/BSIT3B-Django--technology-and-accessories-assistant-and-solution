(function () {
  'use strict';

  var MAX_ATTACHMENTS = 5;
  var MAX_FILE_BYTES = 10 * 1024 * 1024;
  var MAX_TOTAL_BYTES = 25 * 1024 * 1024;
  var ALLOWED_EXTENSIONS = [
    'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp',
    'pdf', 'txt', 'md', 'csv',
    'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'zip'
  ];
  var IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'];

  function extensionOf(name) {
    var match = /\.([a-z0-9]+)$/i.exec(name || '');
    return match ? match[1].toLowerCase() : '';
  }

  function isImageName(name) {
    return IMAGE_EXTENSIONS.indexOf(extensionOf(name)) !== -1;
  }

  function formatSize(bytes) {
    if (typeof bytes !== 'number' || bytes < 0) return '';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function create(root, options) {
    if (!root) return null;
    options = options || {};

    var toggle = root.querySelector('[data-attach-toggle]');
    var menu = root.querySelector('[data-attach-menu]');
    var pick = root.querySelector('[data-attach-pick]');
    var fileInput = root.querySelector('[data-attach-file]');
    var preview = options.preview || root.querySelector('[data-attach-preview]');
    var pending = [];
    var nextId = 1;

    function setStatus(message) {
      if (typeof options.onStatus === 'function') {
        options.onStatus(message || '');
      }
    }

    function setMenuOpen(open) {
      if (!menu) return;
      menu.hidden = !open;
      if (toggle) toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    function makeFileIcon(className) {
      var icon = document.createElement('span');
      icon.className = className;
      icon.innerHTML = '<i class="fa-solid fa-file-lines" aria-hidden="true"></i>';
      return icon;
    }

    function removeItem(id) {
      pending = pending.filter(function (item) { return item.id !== id; });
      render();
      setStatus('');
    }

    function render() {
      if (!preview) return;
      while (preview.firstChild) preview.removeChild(preview.firstChild);

      pending.forEach(function (item) {
        var chip = document.createElement('div');
        chip.className = 'composer-file';

        if (item.isImage) {
          var thumb = document.createElement('img');
          thumb.className = 'composer-file-thumb';
          thumb.src = item.url;
          thumb.alt = '';
          chip.appendChild(thumb);
        } else {
          chip.appendChild(makeFileIcon('composer-file-icon'));
        }

        var copy = document.createElement('span');
        copy.className = 'composer-file-copy';

        var name = document.createElement('span');
        name.className = 'composer-file-name';
        name.textContent = item.name;
        copy.appendChild(name);

        var size = document.createElement('span');
        size.className = 'composer-file-size';
        size.textContent = formatSize(item.size);
        copy.appendChild(size);

        chip.appendChild(copy);

        var remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'composer-file-remove';
        remove.title = 'Remove file';
        remove.setAttribute('aria-label', 'Remove ' + item.name);
        remove.innerHTML = '<i class="fa-solid fa-xmark" aria-hidden="true"></i>';
        remove.addEventListener('click', function () { removeItem(item.id); });
        chip.appendChild(remove);

        preview.appendChild(chip);
      });

      preview.hidden = pending.length === 0;
    }

    function addFiles(fileList) {
      var files = Array.prototype.slice.call(fileList || []);
      if (!files.length) return;

      for (var index = 0; index < files.length; index += 1) {
        var extension = extensionOf(files[index].name);
        if (ALLOWED_EXTENSIONS.indexOf(extension) === -1) {
          setStatus('"' + files[index].name + '" is not a supported file type.');
          return;
        }
        if (files[index].size > MAX_FILE_BYTES) {
          setStatus('"' + files[index].name + '" is larger than 10 MB.');
          return;
        }
      }

      if (pending.length + files.length > MAX_ATTACHMENTS) {
        setStatus('You can attach up to ' + MAX_ATTACHMENTS + ' files at a time.');
        return;
      }

      var total = pending.reduce(function (sum, item) { return sum + item.size; }, 0)
        + files.reduce(function (sum, file) { return sum + file.size; }, 0);
      if (total > MAX_TOTAL_BYTES) {
        setStatus('Attachments must be 25 MB or smaller in total.');
        return;
      }

      files.forEach(function (file) {
        pending.push({
          id: nextId++,
          file: file,
          name: file.name,
          size: file.size,
          isImage: isImageName(file.name),
          url: URL.createObjectURL(file)
        });
      });

      setStatus('');
      render();
    }

    function renderMessageAttachments(container, attachments) {
      if (!container || !attachments || !attachments.length) return;

      var wrap = document.createElement('div');
      wrap.className = 'chat-attachments';

      attachments.forEach(function (item) {
        var link = document.createElement('a');
        link.className = 'chat-attachment' + (item.isImage ? ' chat-attachment-image' : '');
        link.href = item.url;
        link.target = '_blank';
        link.rel = 'noopener';

        if (item.isImage) {
          var image = document.createElement('img');
          image.src = item.url;
          image.alt = item.name;
          image.loading = 'lazy';
          link.appendChild(image);

          var imageName = document.createElement('span');
          imageName.className = 'chat-attachment-name';
          imageName.textContent = item.name;
          link.appendChild(imageName);
        } else {
          link.appendChild(makeFileIcon('chat-attachment-file'));

          var copy = document.createElement('span');
          copy.className = 'chat-attachment-copy';

          var name = document.createElement('span');
          name.className = 'chat-attachment-name';
          name.textContent = item.name;
          copy.appendChild(name);

          var size = document.createElement('span');
          size.className = 'chat-attachment-size';
          size.textContent = formatSize(item.size);
          copy.appendChild(size);

          link.appendChild(copy);
        }

        wrap.appendChild(link);
      });

      container.appendChild(wrap);
    }

    if (toggle) {
      toggle.addEventListener('click', function (event) {
        event.stopPropagation();
        setMenuOpen(menu ? menu.hidden : false);
      });
    }

    if (pick) {
      pick.addEventListener('click', function () {
        setMenuOpen(false);
        if (fileInput) fileInput.click();
      });
    }

    if (fileInput) {
      fileInput.addEventListener('change', function () {
        addFiles(fileInput.files);
        fileInput.value = '';
      });
    }

    document.addEventListener('click', function (event) {
      if (!menu || menu.hidden) return;
      var target = event.target;
      if (target instanceof Node && (menu.contains(target) || (toggle && toggle.contains(target)))) {
        return;
      }
      setMenuOpen(false);
    });

    document.addEventListener('keydown', function (event) {
      if (event.key !== 'Escape' || !menu || menu.hidden) return;
      setMenuOpen(false);
      if (toggle) toggle.focus();
    });

    return {
      files: function () {
        return pending.map(function (item) { return item.file; });
      },
      snapshot: function () {
        return pending.slice();
      },
      clear: function () {
        pending = [];
        render();
      },
      closeMenu: function () {
        setMenuOpen(false);
      },
      renderMessageAttachments: renderMessageAttachments,
      formatSize: formatSize
    };
  }

  window.TechFixAttachments = {
    create: create,
    formatSize: formatSize
  };
})();
