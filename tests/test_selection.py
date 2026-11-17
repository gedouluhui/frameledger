from fractions import Fraction as F
import itertools
import unittest
from frameledger.selection import select_indices, parse_time
from frameledger.errors import InputError


class SelectionTests(unittest.TestCase):
    def test_vfr_differs_by_policy(self):
        stamps=[F(5),F(126,25),F(129,25)]
        self.assertEqual(select_indices(stamps,[F(257,50)],'nearest'),[2])
        self.assertEqual(select_indices(stamps,[F(257,50)],'previous'),[1])

    def test_exact_tie_prefers_earlier(self):
        self.assertEqual(select_indices([F(0),F(1)],[F(1,2)],'nearest'),[0])

    def test_endpoints_and_repetition(self):
        self.assertEqual(select_indices([F(5),F(6)],[F(6),F(5),F(5)],'previous'),[1,0,0])

    def test_handwritten_bruteforce_oracle(self):
        for ticks in itertools.combinations(range(8),3):
            times=list(map(F,ticks))
            requests=[F(n,2) for n in range(2*ticks[0],2*ticks[-1]+1)]
            nearest=[min(range(3),key=lambda i:(abs(times[i]-q),i)) for q in requests]
            previous=[max(i for i in range(3) if times[i]<=q) for q in requests]
            self.assertEqual(select_indices(times,requests,'nearest'),nearest)
            self.assertEqual(select_indices(times,requests,'previous'),previous)

    def test_bad_input_is_rejected(self):
        for times,queries,policy in [([], [F(0)],'nearest'),([F(0)],[],'nearest'),
                ([F(0),F(0)],[F(0)],'nearest'),([F(1),F(0)],[F(0)],'nearest'),
                ([F(0),F(1)],[F(2)],'nearest'),([F(0),F(1)],[F(-1)],'previous'),
                ([0.,1.],[F(0)],'nearest'),([F(0)],[True],'nearest'),
                ([F(0)],[F(0)],'approximate')]:
            with self.subTest(times=times,queries=queries),self.assertRaises(InputError):
                select_indices(times,queries,policy)

    def test_exact_decimal_and_rational_parse(self):
        self.assertEqual(parse_time('0.14'),F(7,50))
        self.assertEqual(parse_time('1/3'),F(1,3))
        self.assertEqual(parse_time('-5'),F(-5))
        for value in ['NaN','inf','1/0','',True,0.14,'1'*1000]:
            with self.subTest(value=value),self.assertRaises(InputError):parse_time(value)


if __name__=='__main__':unittest.main()
