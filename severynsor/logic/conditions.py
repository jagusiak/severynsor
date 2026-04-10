from abc import ABC, abstractmethod
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Min, Max

class Condition(ABC):
    def __init__(self, args=None):
        self.args = args or []

    @staticmethod
    def from_dict(data):
        if not isinstance(data, dict):
            return ConstantCondition(data)
        
        op = data.get('op')
        args = data.get('args', [])
        
        # Registry of operators
        registry = {
            'AND': AndCondition,
            'OR': OrCondition,
            'NOT': NotCondition,
            '>': GreaterThanCondition,
            '>=': GreaterEqualCondition,
            '<': LessThanCondition,
            '<=': LessEqualCondition,
            '==': EqualCondition,
            '!=': NotEqualCondition,
            'current_value': CurrentValueCondition,
            'constant': ConstantCondition,
            'aggregate': AggregateCondition,
            'time_aggregate': TimeAggregateCondition,
            '+': AddCondition,
            '-': SubCondition,
            '*': MulCondition,
            '/': DivCondition,
        }
        
        klass = registry.get(op)
        if not klass:
            raise ValueError(f"Unknown operator: {op}")
            
        return klass(args)

    def to_dict(self):
        return {
            'op': self.get_op(),
            'args': [arg.to_dict() if isinstance(arg, Condition) else arg for arg in self.args]
        }

    @abstractmethod
    def get_op(self):
        pass

    @abstractmethod
    def eval(self, sensor):
        pass

class AndCondition(Condition):
    def get_op(self): return 'AND'
    def eval(self, sensor):
        return all(Condition.from_dict(arg).eval(sensor) for arg in self.args)

class OrCondition(Condition):
    def get_op(self): return 'OR'
    def eval(self, sensor):
        return any(Condition.from_dict(arg).eval(sensor) for arg in self.args)

class NotCondition(Condition):
    def get_op(self): return 'NOT'
    def eval(self, sensor):
        if not self.args: return True
        return not Condition.from_dict(self.args[0]).eval(sensor)

class BinOpCondition(Condition):
    @abstractmethod
    def compare(self, v1, v2):
        pass

    def eval(self, sensor):
        if len(self.args) < 2: return False
        v1 = Condition.from_dict(self.args[0]).eval(sensor)
        v2 = Condition.from_dict(self.args[1]).eval(sensor)
        return self.compare(v1, v2)

class GreaterThanCondition(BinOpCondition):
    def get_op(self): return '>'
    def compare(self, v1, v2): return v1 > v2

class GreaterEqualCondition(BinOpCondition):
    def get_op(self): return '>='
    def compare(self, v1, v2): return v1 >= v2

class LessThanCondition(BinOpCondition):
    def get_op(self): return '<'
    def compare(self, v1, v2): return v1 < v2

class LessEqualCondition(BinOpCondition):
    def get_op(self): return '<='
    def compare(self, v1, v2): return v1 <= v2

class EqualCondition(BinOpCondition):
    def get_op(self): return '=='
    def compare(self, v1, v2): return v1 == v2

class NotEqualCondition(BinOpCondition):
    def get_op(self): return '!='
    def compare(self, v1, v2): return v1 != v2

class MathOpCondition(Condition):
    @abstractmethod
    def apply(self, v1, v2):
        pass

    def eval(self, sensor):
        if len(self.args) < 2: return 0
        v1 = Condition.from_dict(self.args[0]).eval(sensor)
        v2 = Condition.from_dict(self.args[1]).eval(sensor)
        return self.apply(v1, v2)

class AddCondition(MathOpCondition):
    def get_op(self): return '+'
    def apply(self, v1, v2): return v1 + v2

class SubCondition(MathOpCondition):
    def get_op(self): return '-'
    def apply(self, v1, v2): return v1 - v2

class MulCondition(MathOpCondition):
    def get_op(self): return '*'
    def apply(self, v1, v2): return v1 * v2

class DivCondition(MathOpCondition):
    def get_op(self): return '/'
    def apply(self, v1, v2): 
        if v2 == 0: return 0
        return v1 / v2

class CurrentValueCondition(Condition):
    def get_op(self): return 'current_value'
    def eval(self, sensor):
        from severynsor.models import ValueRecord
        last_record = ValueRecord.objects.filter(sensor=sensor).order_by('-timestamp').first()
        return last_record.value if last_record else 0

class ConstantCondition(Condition):
    def get_op(self): return 'constant'
    def eval(self, sensor):
        if isinstance(self.args, list) and len(self.args) > 0:
            return self.args[0]
        return self.args

    def to_dict(self):
        return {'op': 'constant', 'args': self.args}

class AggregateCondition(Condition):
    def get_op(self): return 'aggregate'
    def eval(self, sensor):
        # args[0] = n (last record entries), args[1] = func (sum, min, max)
        if len(self.args) < 2: return 0
        n = int(Condition.from_dict(self.args[0]).eval(sensor))
        func_name = Condition.from_dict(self.args[1]).eval(sensor)
        
        from severynsor.models import ValueRecord
        records = ValueRecord.objects.filter(sensor=sensor).order_by('-timestamp')[:n]
        ids = [r.id for r in records]
        
        aggs = {
            'sum': Sum('value'),
            'min': Min('value'),
            'max': Max('value')
        }
        
        agg_func = aggs.get(func_name.lower())
        if not agg_func: return 0
        
        result = ValueRecord.objects.filter(id__in=ids).aggregate(res=agg_func)['res']
        return result or 0

class TimeAggregateCondition(Condition):
    def get_op(self): return 'time_aggregate'
    def eval(self, sensor):
        # args[0] = n (minutes), args[1] = func (sum, min, max)
        if len(self.args) < 2: return 0
        n = int(Condition.from_dict(self.args[0]).eval(sensor))
        func_name = Condition.from_dict(self.args[1]).eval(sensor)
        
        from severynsor.models import ValueRecord
        last_record = ValueRecord.objects.filter(sensor=sensor).order_by('-timestamp').first()
        if not last_record: return 0
        
        start_time = last_record.timestamp - timedelta(minutes=n)
        
        aggs = {
            'sum': Sum('value'),
            'min': Min('value'),
            'max': Max('value')
        }
        
        agg_func = aggs.get(func_name.lower())
        if not agg_func: return 0
        
        result = ValueRecord.objects.filter(sensor=sensor, timestamp__gte=start_time).aggregate(res=agg_func)['res']
        return result or 0
