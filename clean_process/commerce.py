"""Conservative monetary/discount normalization, preserving original evidence."""
from decimal import Decimal, InvalidOperation
import re

from .contracts import Datum
from .review_recognition import normalize


def decimal_string(value):
    return format(value, 'f').rstrip('0').rstrip('.') if '.' in format(value, 'f') else format(value, 'f')


def money(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    match = re.fullmatch(r'\s*(?:(?P<currency>[A-Z]{3})\s*)?(?P<symbol>US\$|U\$S|\$|€|£)?\s*(?P<number>\d[\d.,]*)\s*', str(value))
    if not match:
        return None
    number = match['number']
    if ',' in number and '.' in number:
        separator = ',' if number.rfind(',') > number.rfind('.') else '.'
        grouping = '.' if separator == ',' else ','
        integer, fraction = number.rsplit(separator, 1)
        if not re.fullmatch(r'\d{1,3}(?:' + re.escape(grouping) + r'\d{3})+', integer) or not re.fullmatch(r'\d{1,2}', fraction):
            return None
        number = integer.replace(grouping, '') + '.' + fraction
    elif ',' in number or '.' in number:
        separator = ',' if ',' in number else '.'
        if number.count(separator) != 1 or len(number.split(separator)[1]) not in (1, 2):
            return None  # Three digits could be a decimal or a thousands group.
        number = number.replace(separator, '.')
    try:
        amount = Decimal(number)
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount < 0:
        return None
    currency = match['currency'] or ('USD' if match['symbol'] in ('US$', 'U$S') else None)
    return {'amount': decimal_string(amount), 'symbol': match['symbol'], 'currency': currency}


def percentage(value, *, explicit_numeric=False):
    text = str(value).strip()
    match = re.fullmatch(r'(?:%\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*%)(?:\s*(?:off|de descuento|descuento))?', text, re.IGNORECASE)
    numeric = next((v for v in match.groups() if v is not None), None) if match else text if explicit_numeric and re.fullmatch(r'\d+(?:[.,]\d+)?', text) else None
    if numeric is None:
        return None
    amount = Decimal(numeric.replace(',', '.'))
    return decimal_string(amount) if amount.is_finite() and 0 <= amount <= 100 else None


def enrich_commerce(unit):
    """Normalize interpreted fields only; caller keeps the original Unit in Evidence."""
    issues = []
    result = []
    derived = []
    for datum in unit.fields:
        prop = datum.property
        source_class = normalize(datum.locator.get('producer_class', ''))
        if prop == 'amount' and source_class in ('previous price', 'old price', 'original price', 'precio anterior', 'regular price'):
            prop = 'previous_amount'
        if prop in ('amount', 'previous_amount', 'discount_amount'):
            parsed = money(datum.value)
            # A producer-independent canonical decimal is already explicit.
            canonical = not datum.locator.get('producer_class') and isinstance(datum.value, str) and re.fullmatch(r'\d+(?:\.\d+)?', datum.value)
            if parsed:
                datum = Datum(property=prop, value=parsed['amount'], method='interpretation',
                    locator={**datum.locator, 'original_property': datum.property,
                             'original_literal': datum.value, 'recognition_rule': 'monetary_literal'})
                for field, value in [('currency_symbol', parsed['symbol']), ('currency', parsed['currency'])]:
                    if value is not None:
                        derived.append(Datum(property=field, value=value, method='interpretation', locator=datum.locator))
            elif not canonical:
                issues.append({'property': prop, 'value': datum.value, 'reason': 'ambiguous_monetary_literal'})
                result.append(Datum(property='raw_field', value={'name': prop, 'value': datum.value}, locator=datum.locator))
                continue
        result.append(datum)
    unit.fields = result
    def values(prop):
        return [f.value for f in unit.fields if f.property == prop]
    def add(prop, value, rule):
        if value is not None and value not in values(prop):
            unit.fields.append(Datum(property=prop, value=value, method='interpretation',
                                     locator={'recognition_rule': rule}))
    for field in derived:
        if field.value not in values(field.property):
            unit.fields.append(field)
    if values('amount') and not values('price_kind'):
        add('price_kind', 'exact', 'explicit_current_amount')
    statuses = [s for s in values('discount_status') if isinstance(s, str) and s in ('discount', 'no_discount', 'unknown', 'conflict')]
    for prop in ('discount_percent', 'discount_amount'):
        for value in values(prop):
            try:
                amount = Decimal(str(value))
                if amount.is_finite() and amount >= 0 and (prop != 'discount_percent' or amount <= 100):
                    statuses.append('discount' if amount > 0 else 'no_discount')
            except InvalidOperation:
                pass
    previous, current, currencies = values('previous_amount'), values('amount'), {v for v in values('currency') if isinstance(v, str)}
    if len(previous) == len(current) == len(currencies) == 1:
        before, after = Decimal(str(previous[0])), Decimal(str(current[0]))
        statuses.append('discount' if after < before else 'no_discount')
        if before > 0 and after < before:
            calculated = (100 * (before-after) / before).quantize(Decimal('0.01'))
            advertised = [v for v in values('discount_percent') if isinstance(v, str) and re.fullmatch(r'\d+(?:\.\d+)?', v) and 0 <= Decimal(v) <= 100]
            if advertised and any(abs(Decimal(str(v))-calculated) > Decimal('0.01') for v in advertised):
                statuses.append('conflict')
                issues.append({'reason': 'discount_percentage_disagrees_with_prices', 'calculated_percent': str(calculated)})
            elif not advertised:
                add('discount_percent', decimal_string(calculated), 'same_offer_same_explicit_currency_prices')
    known = set(statuses)-{'unknown'}
    if 'conflict' in known or len(known) > 1:
        issues.append({'reason': 'contradictory_discount_evidence', 'evidence_states': statuses})
        unit.fields = [f for f in unit.fields if f.property != 'discount_status']
        add('discount_status', 'conflict', 'contradictory_discount_evidence')
    elif known:
        unit.fields = [f for f in unit.fields if f.property != 'discount_status' or f.value != 'unknown']
        add('discount_status', next(iter(known)), 'explicit_discount_evidence')
    elif unit.classification == 'Oferta' or values('amount') or values('discount_percent'):
        add('discount_status', 'unknown', 'absence_of_discount_evidence_is_not_no_discount')
    return issues
