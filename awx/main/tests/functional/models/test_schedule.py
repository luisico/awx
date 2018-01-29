from datetime import datetime

import mock
import pytest
import pytz

from awx.main.models import JobTemplate, Schedule


@pytest.fixture
def job_template(inventory, project):
    # need related resources set for these tests
    return JobTemplate.objects.create(
        name='test-job_template',
        inventory=inventory,
        project=project
    )


@pytest.mark.django_db
def test_repeats_forever(job_template):
    s = Schedule(
        name='Some Schedule',
        rrule='DTSTART:20300112T210000Z RRULE:FREQ=DAILY;INTERVAL=1',
        unified_job_template=job_template
    )
    s.save()
    assert str(s.next_run) == str(s.dtstart) == '2030-01-12 21:00:00+00:00'
    assert s.dtend is None


@pytest.mark.django_db
def test_no_recurrence_utc(job_template):
    s = Schedule(
        name='Some Schedule',
        rrule='DTSTART:20300112T210000Z RRULE:FREQ=DAILY;INTERVAL=1;COUNT=1',
        unified_job_template=job_template
    )
    s.save()
    assert str(s.next_run) == str(s.dtstart) == str(s.dtend) == '2030-01-12 21:00:00+00:00'


@pytest.mark.django_db
def test_no_recurrence_est(job_template):
    s = Schedule(
        name='Some Schedule',
        rrule='DTSTART;TZID=America/New_York:20300112T210000 RRULE:FREQ=DAILY;INTERVAL=1;COUNT=1',
        unified_job_template=job_template
    )
    s.save()
    assert str(s.next_run) == str(s.dtstart) == str(s.dtend) == '2030-01-13 02:00:00+00:00'


@pytest.mark.django_db
def test_next_run_utc(job_template):
    s = Schedule(
        name='Some Schedule',
        rrule='DTSTART:20300112T210000Z RRULE:FREQ=MONTHLY;INTERVAL=1;BYDAY=SA;BYSETPOS=1;COUNT=4',
        unified_job_template=job_template
    )
    s.save()
    assert str(s.next_run) == '2030-02-02 21:00:00+00:00'
    assert str(s.next_run) == str(s.dtstart)
    assert str(s.dtend) == '2030-05-04 21:00:00+00:00'


@pytest.mark.django_db
def test_next_run_est(job_template):
    s = Schedule(
        name='Some Schedule',
        rrule='DTSTART;TZID=America/New_York:20300112T210000 RRULE:FREQ=MONTHLY;INTERVAL=1;BYDAY=SA;BYSETPOS=1;COUNT=4',
        unified_job_template=job_template
    )
    s.save()

    assert str(s.next_run) == '2030-02-03 02:00:00+00:00'
    assert str(s.next_run) == str(s.dtstart)

    # March 10, 2030 is when DST takes effect in NYC
    assert str(s.dtend) == '2030-05-05 01:00:00+00:00'


@pytest.mark.django_db
def test_year_boundary(job_template):
    rrule = 'DTSTART;TZID=America/New_York:20301231T230000 RRULE:FREQ=YEARLY;INTERVAL=1;BYMONTH=12;BYMONTHDAY=31;COUNT=4'  # noqa
    s = Schedule(
        name='Some Schedule',
        rrule=rrule,
        unified_job_template=job_template
    )
    s.save()

    assert str(s.next_run) == '2031-01-01 04:00:00+00:00'  # UTC = +5 EST
    assert str(s.next_run) == str(s.dtstart)
    assert str(s.dtend) == '2034-01-01 04:00:00+00:00'  # UTC = +5 EST


@pytest.mark.django_db
def test_leap_year_day(job_template):
    rrule = 'DTSTART;TZID=America/New_York:20320229T050000 RRULE:FREQ=YEARLY;INTERVAL=1;BYMONTH=02;BYMONTHDAY=29;COUNT=2'  # noqa
    s = Schedule(
        name='Some Schedule',
        rrule=rrule,
        unified_job_template=job_template
    )
    s.save()

    assert str(s.next_run) == '2032-02-29 10:00:00+00:00'  # UTC = +5 EST
    assert str(s.next_run) == str(s.dtstart)
    assert str(s.dtend) == '2036-02-29 10:00:00+00:00'  # UTC = +5 EST


@pytest.mark.django_db
@pytest.mark.parametrize('until, dtend', [
    ['20180602T170000Z', '2018-06-02 12:00:00+00:00'],
    ['20180602T000000Z', '2018-06-01 12:00:00+00:00'],
])
def test_utc_until(job_template, until, dtend):
    rrule = 'DTSTART:20180601T120000Z RRULE:FREQ=DAILY;INTERVAL=1;UNTIL={}'.format(until)
    s = Schedule(
        name='Some Schedule',
        rrule=rrule,
        unified_job_template=job_template
    )
    s.save()

    assert str(s.next_run) == '2018-06-01 12:00:00+00:00'
    assert str(s.next_run) == str(s.dtstart)
    assert str(s.dtend) == dtend


@pytest.mark.django_db
@pytest.mark.parametrize('dtstart, until', [
    ['20180601T120000Z', '20180602T170000'],
    ['TZID=America/New_York:20180601T120000', '20180602T170000'],
])
def test_tzinfo_naive_until(job_template, dtstart, until):
    rrule = 'DTSTART;{} RRULE:FREQ=DAILY;INTERVAL=1;UNTIL={}'.format(dtstart, until)  # noqa
    s = Schedule(
        name='Some Schedule',
        rrule=rrule,
        unified_job_template=job_template
    )
    with pytest.raises(ValueError):
        s.save()


@pytest.mark.django_db
def test_mismatched_until_timezone(job_template):
    rrule = 'DTSTART;TZID=America/New_York:20180601T120000 RRULE:FREQ=DAILY;INTERVAL=1;UNTIL=20180602T000000' + 'Z'  # noqa the Z isn't allowed, because we have a TZID=America/New_York
    s = Schedule(
        name='Some Schedule',
        rrule=rrule,
        unified_job_template=job_template
    )
    with pytest.raises(ValueError):
        s.save()


@pytest.mark.django_db
def test_utc_until_in_the_past(job_template):
    rrule = 'DTSTART:20180601T120000Z RRULE:FREQ=DAILY;INTERVAL=1;UNTIL=20150101T100000Z'
    s = Schedule(
        name='Some Schedule',
        rrule=rrule,
        unified_job_template=job_template
    )
    s.save()

    assert s.next_run is s.dtstart is s.dtend is None


@pytest.mark.django_db
@mock.patch('awx.main.models.schedules.now', lambda: datetime(2030, 03, 05, tzinfo=pytz.utc))
def test_dst_phantom_hour(job_template):
    # The DST period in the United States begins at 02:00 (2 am) local time, so
    # the hour from 2:00:00 to 2:59:59 does not exist in the night of the
    # switch.

    # Three Sundays, starting 2:30AM America/New_York, starting Mar 3, 2030,
    # (which doesn't exist)
    rrule = 'DTSTART;TZID=America/New_York:20300303T023000 RRULE:FREQ=WEEKLY;BYDAY=SU;INTERVAL=1;COUNT=3'
    s = Schedule(
        name='Some Schedule',
        rrule=rrule,
        unified_job_template=job_template
    )
    s.save()

    # 3/10/30 @ 2:30AM is skipped because it _doesn't exist_ <cue twilight zone music>
    assert str(s.next_run) == '2030-03-17 06:30:00+00:00'


@pytest.mark.django_db
def test_beginning_of_time(job_template):
    # ensure that really large generators don't have performance issues
    rrule = 'DTSTART:19700101T000000Z RRULE:FREQ=MINUTELY;INTERVAL=1'
    s = Schedule(
        name='Some Schedule',
        rrule=rrule,
        unified_job_template=job_template
    )
    with pytest.raises(ValueError):
        s.save()
