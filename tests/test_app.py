import os
import tempfile
import unittest
from pathlib import Path

# Import the application with a separate database; never write to the office database.
_test_directory = tempfile.TemporaryDirectory(prefix='ruang-test-')
_previous_url = os.environ.get('DATABASE_URL')
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(_test_directory.name) / 'booking.db')
from app import app, db, Booking, DAYS, local_now
if _previous_url is None:
    del os.environ['DATABASE_URL']
else:
    os.environ['DATABASE_URL'] = _previous_url


class BookingTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        with app.app_context():
            db.session.query(Booking).delete()
            db.session.commit()
        self.client.get('/add')
        with self.client.session_transaction() as session:
            self.token = session['csrf_token']
        self.form = dict(room='Room 1', date=local_now().date().isoformat(),
                         start_time='09:00', end_time='10:00', md_name='Dimas',
                         supplier_name='PT Mitra', csrf_token=self.token)

    def post(self, path='/add', **changes):
        return self.client.post(path, data={**self.form, **changes})

    def test_dashboard_and_views(self):
        for path in ('/', '/?view=list', '/?scope=all', '/?date=invalid',
                     '/?room=Room+2', '/?q=Dimas&scope=all', '/add'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_create_adjacent_and_other_room(self):
        self.assertEqual(self.post().status_code, 302)
        self.assertEqual(self.post(start_time='10:00', end_time='11:00').status_code, 302)
        self.assertEqual(self.post(room='Room 2').status_code, 302)
        with app.app_context():
            self.assertEqual(Booking.query.count(), 3)
            self.assertEqual(Booking.query.first().day, DAYS[local_now().weekday()])

    def test_conflict_preserves_form_values(self):
        self.post()
        result = self.post(start_time='09:30', end_time='11:00', md_name='Budi')
        self.assertEqual(result.status_code, 422)
        self.assertIn('value="Budi"', result.text)
        self.assertIn('sudah dibooking', result.text)
        with app.app_context():
            self.assertEqual(Booking.query.count(), 1)

    def test_invalid_inputs(self):
        for changes in (dict(end_time='08:00'), dict(end_time='09:00'),
                        dict(date='invalid'), dict(start_time='25:00'),
                        dict(room='Unknown'), dict(md_name='   '),
                        dict(supplier_name='X' * 101)):
            with self.subTest(changes=changes):
                self.assertEqual(self.post(**changes).status_code, 422)
        with app.app_context():
            self.assertEqual(Booking.query.count(), 0)

    def test_edit_rejects_conflict_without_changing_existing(self):
        self.post()
        self.post(start_time='11:00', end_time='12:00', md_name='Budi')
        with app.app_context():
            booking_id = Booking.query.filter_by(md_name='Budi').first().id
        self.assertEqual(self.post(f'/edit/{booking_id}', md_name='Changed').status_code, 422)
        with app.app_context():
            booking = db.session.get(Booking, booking_id)
            self.assertEqual(booking.md_name, 'Budi')
            self.assertEqual(booking.start_time.hour, 11)
        self.assertEqual(self.client.get(f'/edit/{booking_id}').status_code, 200)
        self.assertEqual(self.post(f'/edit/{booking_id}', start_time='12:00', end_time='13:00',
                                   md_name='Budi').status_code, 302)

    def test_csrf_and_post_only_delete(self):
        self.assertEqual(self.post(csrf_token='wrong').status_code, 400)
        self.post()
        with app.app_context():
            booking_id = Booking.query.first().id
        self.assertEqual(self.client.get(f'/delete/{booking_id}').status_code, 405)
        self.assertEqual(self.client.post(f'/delete/{booking_id}').status_code, 400)
        self.assertEqual(self.client.post(f'/delete/{booking_id}', data={'csrf_token': self.token}).status_code, 302)
        with app.app_context():
            self.assertEqual(Booking.query.count(), 0)

    def test_search_and_date_filter(self):
        self.post()
        self.post(room='Room 2', md_name='Budi', supplier_name='Tamu Lain')
        result = self.client.get('/?scope=all&q=Dimas')
        self.assertIn('PT Mitra', result.text)
        self.assertNotIn('Tamu Lain', result.text)
        result = self.client.get('/?date=2020-01-01&view=list')
        self.assertIn('Belum ada booking', result.text)
        self.assertNotIn('PT Mitra', result.text)


if __name__ == '__main__':
    unittest.main()
