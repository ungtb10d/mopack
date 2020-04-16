import yaml
from io import StringIO
from textwrap import dedent
from unittest import TestCase
from yaml.error import MarkedYAMLError

from mopack.yaml_loader import *


class TestMakeYamlError(TestCase):
    def test_make(self):
        data = StringIO('&')
        try:
            yaml.safe_load(data)
        except MarkedYAMLError as e:
            err = make_yaml_error(e, data)
            self.assertEqual(err.snippet, '&')
            self.assertEqual(err.mark.line, 0)
            self.assertEqual(err.mark.column, 1)
            self.assertRegex(str(err), '(?m)^  &\n   \\^$')


class TestMarkedList(TestCase):
    def test_init(self):
        m = MarkedList()
        self.assertEqual(m, [])
        self.assertEqual(m.mark, None)
        self.assertEqual(m.marks, [])

        m = MarkedList('mark')
        self.assertEqual(m, [])
        self.assertEqual(m.mark, 'mark')
        self.assertEqual(m.marks, [])

    def test_append(self):
        m = MarkedList()
        m.append(1, 'mark1')
        self.assertEqual(m, [1])
        self.assertEqual(m.marks, ['mark1'])

        m[-1:] = [1, 2, 3]
        self.assertEqual(m, [1, 2, 3])
        self.assertEqual(m.marks, ['mark1'])

        m.append(4, 'mark4')
        self.assertEqual(m, [1, 2, 3, 4])
        self.assertEqual(m.marks, ['mark1', None, None, 'mark4'])

    def test_extend(self):
        m = MarkedList()
        m.extend([1, 2, 3])
        self.assertEqual(m, [1, 2, 3])
        self.assertEqual(m.mark, None)
        self.assertEqual(m.marks, [None, None, None])

        m2 = MarkedList('mark')
        m2.append(4, 'mark4')
        m.extend(m2)
        self.assertEqual(m, [1, 2, 3, 4])
        self.assertEqual(m.mark, 'mark')
        self.assertEqual(m.marks, [None, None, None, 'mark4'])

        m3 = MarkedList('badmark')
        m.extend(m3)
        self.assertEqual(m, [1, 2, 3, 4])
        self.assertEqual(m.mark, 'mark')
        self.assertEqual(m.marks, [None, None, None, 'mark4'])

    def test_copy(self):
        m = MarkedList('mark')
        m.append(1, 'mark1')

        m2 = m.copy()
        self.assertEqual(m2, [1])
        self.assertEqual(m2.mark, 'mark')
        self.assertEqual(m2.marks, ['mark1'])


class TestMarkedDict(TestCase):
    def test_init(self):
        m = MarkedDict()
        self.assertEqual(m, {})
        self.assertEqual(m.mark, None)
        self.assertEqual(m.marks, {})

        m = MarkedDict('mark')
        self.assertEqual(m, {})
        self.assertEqual(m.mark, 'mark')
        self.assertEqual(m.marks, {})

    def test_add(self):
        m = MarkedDict()
        m.add('key1', 1, 'mark1')
        self.assertEqual(m, {'key1': 1})
        self.assertEqual(m.marks, {'key1': 'mark1'})

    def test_update(self):
        m = MarkedDict()
        m.update({'key1': 1, 'key2': 2})
        self.assertEqual(m, {'key1': 1, 'key2': 2})
        self.assertEqual(m.mark, None)
        self.assertEqual(m.marks, {})

        m2 = MarkedDict('mark')
        m.add('key3', 3, 'mark3')
        m.update(m2)
        self.assertEqual(m, {'key1': 1, 'key2': 2, 'key3': 3})
        self.assertEqual(m.mark, 'mark')
        self.assertEqual(m.marks, {'key3': 'mark3'})

        m3 = MarkedDict('badmark')
        m.update(m3)
        self.assertEqual(m, {'key1': 1, 'key2': 2, 'key3': 3})
        self.assertEqual(m.mark, 'mark')
        self.assertEqual(m.marks, {'key3': 'mark3'})

    def test_copy(self):
        m = MarkedDict('mark')
        m.add('key1', 1, 'mark1')

        m2 = m.copy()
        self.assertEqual(m2, {'key1': 1})
        self.assertEqual(m2.mark, 'mark')
        self.assertEqual(m2.marks, {'key1': 'mark1'})


class TestSafeLineLoader(TestCase):
    def test_mapping(self):
        data = yaml.load(dedent("""
        house:
          cat: 1
          dog: 2
        zoo:
          panda: 3
          giraffe: 4
        """).strip(), Loader=SafeLineLoader)

        self.assertEqual(data, {'house': {'cat': 1, 'dog': 2},
                                'zoo': {'panda': 3, 'giraffe': 4}})

        self.assertEqual(data.mark.line, 0)
        self.assertEqual(data.mark.column, 0)
        self.assertEqual({k: (v.line, v.column)
                          for k, v in data.marks.items()},
                         {'house': (0, 0), 'zoo': (3, 0)})

        self.assertEqual(data['house'].mark.line, 1)
        self.assertEqual(data['house'].mark.column, 2)
        self.assertEqual({k: (v.line, v.column)
                          for k, v in data['house'].marks.items()},
                         {'cat': (1, 2), 'dog': (2, 2)})

        self.assertEqual(data['zoo'].mark.line, 4)
        self.assertEqual(data['zoo'].mark.column, 2)
        self.assertEqual({k: (v.line, v.column)
                          for k, v in data['zoo'].marks.items()},
                         {'panda': (4, 2), 'giraffe': (5, 2)})

    def test_sequence(self):
        data = yaml.load(dedent("""
        - - A1
          - A2
        - - B1
          - B2
        """).strip(), Loader=SafeLineLoader)

        self.assertEqual(data, [['A1', 'A2'], ['B1', 'B2']])

        self.assertEqual(data.mark.line, 0)
        self.assertEqual(data.mark.column, 0)
        self.assertEqual([(i.line, i.column) for i in data.marks],
                         [(0, 2), (2, 2)])

        self.assertEqual(data[0].mark.line, 0)
        self.assertEqual(data[0].mark.column, 2)
        self.assertEqual([(i.line, i.column) for i in data[0].marks],
                         [(0, 4), (1, 4)])

        self.assertEqual(data[1].mark.line, 2)
        self.assertEqual(data[1].mark.column, 2)
        self.assertEqual([(i.line, i.column) for i in data[1].marks],
                         [(2, 4), (3, 4)])