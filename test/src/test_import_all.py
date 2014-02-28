

import os
import unittest
import ooi.testing

class TestOOIImports(ooi.testing.ImportTest):
    def __init__(self,*a,**b):
        # for utilities project only, want to search in BASE/src
        # but this test is in BASE/test/src
        # so have to go up two levels, then down to src
        target_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),'src')
        if not target_dir[0]=='/':
            target_dir = os.getcwd() + '/' + target_dir
        print 'target: ' + target_dir
        super(TestOOIImports,self).__init__(target_dir, 'ape', *a, **b)

if __name__ == '__main__':
    unittest.main()