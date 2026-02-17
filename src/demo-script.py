def CalculateAverage(numbers=[]):
    sum = 0

    for i in range(len(numbers)):

        sum += numbers[i]

        if len(numbers) == 0:

            return 0

    average = sum / len(numbers)

    return round(average, 2)


print(CalculateAverage([1, 2, 3]))
