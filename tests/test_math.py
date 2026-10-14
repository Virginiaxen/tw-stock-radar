import unittest
from scripts.build_data import ma,rsi,finite
class TestMath(unittest.TestCase):
 def test_ma(self):
  self.assertEqual(ma([1,2,3,4],2),3.5)
  self.assertIsNone(ma([1],2))
 def test_rsi(self):
  self.assertEqual(rsi(list(range(20))),100)
 def test_finite(self):
  self.assertIsNone(finite('nan'))
  self.assertEqual(finite('1,234'),1234)
if __name__=='__main__':unittest.main()
