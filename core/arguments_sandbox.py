def f1(arg1, arg2):
    return arg1 * arg2


def f2(*args, **kwargs):
    print(args)
    print(kwargs)
    return f1(*args, **kwargs)


f2(arg1=10, arg2=20)


def f3(arg1, *args):
    if arg1:
        print("Arg1: ", arg1)
    if args:
        print("Args:")
        for x in args:
            print(x)


def f4(arg1, arg2=1000, *args):
    f1(arg1)
    f1(arg2)
    f1(*args)
