(() => {
    'use strict';
    document.querySelectorAll('[data-dismiss]').forEach(button => {
        button.addEventListener('click', () => button.closest('.alert').remove());
    });
    document.querySelectorAll('[data-auto-submit]').forEach(input => {
        input.addEventListener('change', () => { if (input.value && input.validity.valid) input.form.requestSubmit(); });
    });
    document.querySelectorAll('form[data-confirm]').forEach(form => {
        form.addEventListener('submit', event => {
            if (!window.confirm(form.dataset.confirm)) event.preventDefault();
        });
    });
    // Registered after the confirm handlers so a cancelled confirm leaves the buttons usable.
    document.querySelectorAll('form[method="post"]').forEach(form => {
        form.addEventListener('submit', event => {
            if (event.defaultPrevented) return;
            if (form.dataset.submitting) {
                event.preventDefault();
                return;
            }
            form.dataset.submitting = 'true';
            const buttons = [...form.querySelectorAll('button[type="submit"]:not([form])'), ...(form.id ? document.querySelectorAll(`button[form="${form.id}"]`) : [])];
            buttons.forEach(button => { button.disabled = true; });
        });
    });
    window.addEventListener('pageshow', event => {
        if (!event.persisted) return;
        document.querySelectorAll('form[data-submitting]').forEach(form => { delete form.dataset.submitting; });
        document.querySelectorAll('button[type="submit"]:disabled').forEach(button => { button.disabled = false; });
    });

    const refreshPanel = document.querySelector('[data-auto-refresh]');
    if (refreshPanel) {
        const localDate = () => new Intl.DateTimeFormat('en-CA', {timeZone: refreshPanel.dataset.timezone, year: 'numeric', month: '2-digit', day: '2-digit'}).format(new Date());
        // Reception keeps this page open all day; reload so statuses and other desks' bookings stay current.
        const refreshAfter = 3 * 60 * 1000;
        let lastActivity = Date.now();
        ['pointerdown', 'keydown', 'wheel', 'touchstart'].forEach(type => {
            window.addEventListener(type, () => { lastActivity = Date.now(); }, {capture: true, passive: true});
        });
        const search = document.querySelector('.search-form input[name="q"]');
        window.setInterval(() => {
            if (Date.now() - lastActivity < refreshAfter || document.hidden) return;
            if (document.querySelector('dialog[open]')) return;
            if (search && (document.activeElement === search || search.value !== search.defaultValue)) return;
            const {selectedDate, today} = refreshPanel.dataset;
            if (selectedDate === today && localDate() !== today) {
                const url = new URL(window.location.href);
                url.searchParams.delete('date');
                window.location.assign(url);
            } else {
                window.location.reload();
            }
        }, 30000);
    }

    const dialog = document.querySelector('#booking-detail');
    const bookingData = document.querySelector('#booking-data');
    if (dialog && bookingData && typeof dialog.showModal === 'function') {
        const bookings = new Map(JSON.parse(bookingData.textContent).map(booking => [String(booking.id), booking]));
        document.querySelectorAll('[data-booking-id]').forEach(link => {
            link.addEventListener('click', event => {
                if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
                const booking = bookings.get(link.dataset.bookingId);
                if (!booking) return;
                event.preventDefault();
                const setText = (id, value) => { document.getElementById(id).textContent = value; };
                setText('detail-title', `Meeting ${booking.room}`);
                setText('detail-status', booking.status);
                setText('detail-date', `${booking.day}, ${booking.date}`);
                setText('detail-time', `${booking.start} – ${booking.end}`);
                setText('detail-md', booking.md);
                setText('detail-supplier', booking.supplier);
                document.getElementById('detail-edit').href = booking.edit_url;
                document.getElementById('detail-delete-form').action = booking.delete_url;
                dialog.className = `dialog ${booking.tone}`;
                dialog.showModal();
            });
        });
        dialog.querySelector('[data-close-dialog]').addEventListener('click', () => dialog.close());
        dialog.addEventListener('click', event => {
            if (event.target !== dialog) return;
            const bounds = dialog.getBoundingClientRect();
            if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
        });
    }

    const form = document.querySelector('#booking-form');
    if (form) {
        const dateInput = form.elements.date;
        const startInput = form.elements.start_time;
        const endInput = form.elements.end_time;
        const duration = document.querySelector('#duration-hint');
        const updateHints = () => {
            const chosenDate = dateInput.value ? new Date(`${dateInput.value}T12:00:00`) : null;
            document.getElementById('date-day').textContent = chosenDate && !Number.isNaN(chosenDate.getTime()) ? new Intl.DateTimeFormat('id-ID', {weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'}).format(chosenDate) : '';
            let message = '';
            let invalid = false;
            if (startInput.value && endInput.value) {
                const minutes = value => Number(value.slice(0, 2)) * 60 + Number(value.slice(3, 5));
                const difference = minutes(endInput.value) - minutes(startInput.value);
                invalid = difference <= 0;
                if (invalid) message = 'Jam selesai harus setelah jam mulai.';
                else message = `Durasi ${Math.floor(difference / 60) ? `${Math.floor(difference / 60)} jam ` : ''}${difference % 60 ? `${difference % 60} menit` : ''}`.trim();
            }
            endInput.setCustomValidity(invalid ? 'Jam selesai harus setelah jam mulai.' : '');
            duration.querySelector('span').textContent = message;
            duration.classList.toggle('invalid', invalid);
            duration.hidden = !message;
        };
        form.addEventListener('input', updateHints);
        form.addEventListener('change', updateHints);
        updateHints();
    }
})();
