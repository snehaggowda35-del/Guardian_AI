from backend.app.agents import assess, classify

def test_safe_language_is_minimized():
    assert classify('Best Java sorting algorithms')[0] == 'normal'
    assert classify('I am dying laughing')[0] == 'normal'

def test_high_risk_creates_alert():
    result = assess('ways to hurt myself', [])
    assert result.alert is True
    assert result.severity == 'HIGH'

def test_suicidal_language_creates_alert():
    result = assess("I'm feeling suicidal", [])
    assert result.category == 'suicidal_risk'
    assert result.alert is True

def test_hanging_language_creates_alert():
    result = assess("ill hang myself anf die", [])
    assert result.category == 'suicidal_risk'
    assert result.alert is True

def test_negated_language_is_not_alerted():
    result = assess("I'm not suicidal; this is a prevention lesson", [])
    assert result.category == 'normal'
    assert result.alert is False

def test_explicit_violence_language_creates_alert():
    result = assess("I'll kill someone", [])
    assert result.category == 'violence'
    assert result.alert is True

def test_figurative_death_language_is_not_alerted():
    result = assess("I'll die laughing", [])
    assert result.category == 'normal'
    assert result.alert is False

def test_murder_threat_creates_violence_alert():
    result = assess("I want to murder someone", [])
    assert result.category == 'violence'
    assert result.alert is True

def test_context_escalates_distress():
    class Event: category='emotional_distress'; trigger_text='Nobody cares about me'
    result = assess("I don't want to be alive", [Event(), Event()])
    assert result.severity == 'CRITICAL'
    assert len(result.context) == 2
