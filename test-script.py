
def CalculateAverage(numbers=[]):

    """

    this function calculates average of list

    :param numbers: list of numbers

    :return: average value

    """

    sum = 0 # перекрывает встроенную функцию sum()

    for i in range(len(numbers)): # не pythonic

        sum += numbers[i]

        if len(numbers) == 0:

            return 0 # логическая ошибка: деление проверяется после цикла

    
    average = sum / len(numbers)

    return round(average, 2)    

  
print(CalculateAverage([1, 2, 3])) # 2.0