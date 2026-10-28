import os
import secrets
from datetime import date, datetime, time, timedelta
from functools import wraps
from zoneinfo import ZoneInfo

from flask import (Flask, abort, flash, redirect, render_template, request,
                   session, url_for)
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'sqlite:///meeting_room.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'booking_secret_key')
db = SQLAlchemy(app)

ROOMS = ('Room 1', 'Room 2')
DAYS = ('Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu')
MONTHS = ('Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
          'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember')
TIMEZONE = ZoneInfo('Asia/Jakarta')
DAY_START, DAY_END = time(7), time(18)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room = db.Column(db.String(20), nullable=False)
    day = db.Column(db.String(20), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    md_name = db.Column(db.String(100), nullable=False)
    supplier_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)


with app.app_context():
    db.create_all()


def local_now():
    return datetime.now(TIMEZONE)


def parse_date(value, fallback):
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return fallback


@app.template_filter('date_format')
def date_format(value):
    return f'{value.day} {MONTHS[value.month - 1]} {value.year}'


@app.template_filter('day_name')
def day_name(value):
    return DAYS[value.weekday()]


@app.template_filter('time_format')
def time_format(value):
    return value.strftime('%H:%M')


def csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(32)
    return session['csrf_token']


def protected_post(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if request.method == 'POST':
            token = request.form.get('csrf_token', '')
            if not token or not secrets.compare_digest(token, session.get('csrf_token', '')):
                abort(400, description='Sesi formulir berakhir. Muat ulang halaman lalu coba lagi.')
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def shared_context():
    return dict(rooms=ROOMS, now=local_now(), csrf_token=csrf_token)


def booking_status(booking, now):
    if booking.date < now.date() or (booking.date == now.date() and booking.end_time <= now.time()):
        return 'Selesai'
    if booking.date == now.date() and booking.start_time <= now.time() < booking.end_time:
        return 'Berlangsung'
    return 'Terjadwal'


def booking_json(booking, now):
    return dict(id=booking.id, room=booking.room, date=date_format(booking.date),
                day=day_name(booking.date), start=booking.start_time.strftime('%H:%M'),
                end=booking.end_time.strftime('%H:%M'), md=booking.md_name,
                supplier=booking.supplier_name, status=booking_status(booking, now),
                edit_url=url_for('edit_booking', id=booking.id),
                delete_url=url_for('delete_booking', id=booking.id))


def minutes(value):
    return value.hour * 60 + value.minute


def from_minutes(value):
    return time(value // 60, value % 60)


def room_board(day_bookings, selected_date, now):
    is_today = selected_date == now.date()
    # Gaps that are already over can't be booked; today's free time starts at the next quarter hour.
    earliest = None if selected_date < now.date() else 0
    if is_today:
        earliest = -(-minutes(now) // 15) * 15
    board = []
    for room in ROOMS:
        bookings = [b for b in day_bookings if b.room == room]
        items = []

        def add_gap(start, end):
            if earliest is None:
                return
            start = max(start, earliest)
            if end - start >= 15:
                items.append(dict(kind='free', start=from_minutes(start), end=from_minutes(end),
                                  book_end=from_minutes(min(end, start + 60))))

        cursor = minutes(min([DAY_START] + [b.start_time for b in bookings]))
        for b in bookings:
            add_gap(cursor, minutes(b.start_time))
            items.append(dict(kind='booking', booking=b))
            cursor = max(cursor, minutes(b.end_time))
        add_gap(cursor, minutes(max([DAY_END] + [b.end_time for b in bookings])))

        current = next((b for b in bookings if booking_status(b, now) == 'Berlangsung'), None)
        upcoming = next((b for b in bookings if booking_status(b, now) == 'Terjadwal'), None)
        busy = False
        if not is_today:
            state = f'{len(bookings)} booking' if bookings else 'Kosong'
            note = '' if bookings else 'Belum ada booking'
        elif current:
            busy, state = True, 'Dipakai'
            note = f'sampai {time_format(current.end_time)} · {current.md_name}'
        elif upcoming:
            state = 'Kosong'
            note = f'sampai {time_format(upcoming.start_time)} · berikutnya {upcoming.md_name}'
        else:
            state = 'Kosong'
            note = 'Tidak ada booking lagi hari ini' if bookings else 'Belum ada booking hari ini'
        board.append(dict(room=room, busy=busy, state=state, note=note, items=items))
    return board


@app.route('/')
def index():
    now = local_now()
    selected_date = parse_date(request.args.get('date'), now.date())
    selected_room = request.args.get('room', '')
    if selected_room not in ROOMS:
        selected_room = ''
    scope = 'all' if request.args.get('scope') == 'all' else 'day'
    view = 'list' if scope == 'all' or request.args.get('view') == 'list' else 'schedule'
    search = request.args.get('q', '').strip()[:100]
    query = Booking.query
    if scope == 'day':
        query = query.filter(Booking.date == selected_date)
    if selected_room:
        query = query.filter(Booking.room == selected_room)
    if search:
        query = query.filter(db.or_(Booking.md_name.contains(search, autoescape=True),
                                    Booking.supplier_name.contains(search, autoescape=True)))
    query = query.order_by(Booking.date.desc() if scope == 'all' else Booking.date,
                           Booking.start_time)
    pagination = None
    if scope == 'all':
        pagination = query.paginate(page=request.args.get('page', 1, type=int),
                                    per_page=20, error_out=False)
        bookings = pagination.items
    else:
        bookings = query.all()
    day_bookings = Booking.query.filter_by(date=selected_date).order_by(Booking.start_time).all()
    date_params = dict(room=selected_room, view=view)
    return render_template('index.html', bookings=bookings, day_bookings=day_bookings,
                           selected_date=selected_date, selected_room=selected_room,
                           scope=scope, view=view, search=search, pagination=pagination,
                           previous_url=url_for('index', date=(selected_date - timedelta(days=1) if selected_date > date.min else selected_date).isoformat(), **date_params),
                           next_url=url_for('index', date=(selected_date + timedelta(days=1) if selected_date < date.max else selected_date).isoformat(), **date_params),
                           board=room_board(day_bookings, selected_date, now),
                           booking_status=booking_status,
                           booking_data=[booking_json(b, now) for b in bookings])


def validate_booking(form, booking_id=None):
    values = {key: form.get(key, '').strip() for key in
              ('room', 'date', 'start_time', 'end_time', 'md_name', 'supplier_name')}
    errors = []
    if values['room'] not in ROOMS:
        errors.append(f'Pilih {" atau ".join(ROOMS)}.')
    for field, label in (('md_name', 'Nama pemesan'), ('supplier_name', 'Nama supplier')):
        if not values[field] or len(values[field]) > 100:
            errors.append(f'{label} wajib diisi, maksimal 100 karakter.')
    try:
        parsed_date = date.fromisoformat(values['date'])
        start = datetime.strptime(values['start_time'], '%H:%M').time()
        end = datetime.strptime(values['end_time'], '%H:%M').time()
    except ValueError:
        errors.append('Isi tanggal dan waktu dengan format yang valid.')
        return values, None, errors
    if start >= end:
        errors.append('Jam selesai harus setelah jam mulai pada hari yang sama.')
    if not errors:
        overlap = Booking.query.filter(
            Booking.room == values['room'], Booking.date == parsed_date,
            Booking.start_time < end, Booking.end_time > start)
        if booking_id is not None:
            overlap = overlap.filter(Booking.id != booking_id)
        conflict = overlap.order_by(Booking.start_time).first()
        if conflict:
            errors.append(f'{conflict.room} sudah dibooking {conflict.md_name} pukul '
                          f'{time_format(conflict.start_time)}–{time_format(conflict.end_time)}.')
    data = dict(room=values['room'], date=parsed_date, day=DAYS[parsed_date.weekday()],
                start_time=start, end_time=end, md_name=values['md_name'],
                supplier_name=values['supplier_name'])
    return values, data, errors


@app.route('/add', methods=['GET', 'POST'])
@protected_post
def add_booking():
    errors = []
    if request.method == 'POST':
        values, data, errors = validate_booking(request.form)
        if not errors:
            db.session.add(Booking(**data))
            db.session.commit()
            flash(f"Booking {data['room']} pukul {time_format(data['start_time'])}–"
                  f"{time_format(data['end_time'])} tersimpan.", 'success')
            return redirect(url_for('index', date=data['date'].isoformat()))
    else:
        selected = parse_date(request.args.get('date'), local_now().date())
        values = dict(room=request.args.get('room', 'Room 1'), date=selected.isoformat(),
                      start_time=request.args.get('start_time', ''),
                      end_time=request.args.get('end_time', ''), md_name='', supplier_name='')
    return render_template('booking_form.html', values=values, errors=errors, booking=None), 422 if errors else 200


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@protected_post
def edit_booking(id):
    booking = db.get_or_404(Booking, id)
    errors = []
    if request.method == 'POST':
        values, data, errors = validate_booking(request.form, booking.id)
        if not errors:
            for key, value in data.items():
                setattr(booking, key, value)
            db.session.commit()
            flash('Perubahan disimpan.', 'success')
            return redirect(url_for('index', date=booking.date.isoformat()))
    else:
        values = dict(room=booking.room, date=booking.date.isoformat(),
                      start_time=booking.start_time.strftime('%H:%M'),
                      end_time=booking.end_time.strftime('%H:%M'),
                      md_name=booking.md_name, supplier_name=booking.supplier_name)
    return render_template('booking_form.html', values=values, errors=errors, booking=booking), 422 if errors else 200


@app.route('/delete/<int:id>', methods=['POST'])
@protected_post
def delete_booking(id):
    booking = db.get_or_404(Booking, id)
    selected = booking.date.isoformat()
    message = (f'Booking {booking.md_name} di {booking.room} pukul '
               f'{time_format(booking.start_time)} dibatalkan.')
    db.session.delete(booking)
    db.session.commit()
    flash(message, 'success')
    return redirect(url_for('index', date=selected))


if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')
