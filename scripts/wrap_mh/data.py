from collections import OrderedDict

#define basic command line args
prelim_args_dict = OrderedDict({'age': 'macrodetails/Age',
                                'gender': 'macrodetails/Gender',
                                'race': 'macrodetails/%s', })
prelim_vals_dict = OrderedDict({
    'macrodetails/Asian': 'race',
    'macrodetails/African': 'race',
    'macrodetails/Cacucasian': 'race',
    'macrodetails/Age': 'age',
    'macrodetails/Gender': 'male'
})
