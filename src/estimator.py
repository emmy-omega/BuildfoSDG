from functools import wraps
from datetime import timedelta
from operator import itemgetter
from collections import namedtuple

# feilds for the nameTuples that will constitute the estimate(output)
region_fields = ['name', 'avgAge',
                 'avgDailyIncomeInUSD', 'avgDailyIncomePopulation']
impact_fields = ['currentlyInfected', 'infectionsByRequestedTime', 'severeCasesByRequestedTime',
                 'hospitalBedsByRequestedTime', 'casesForICUByRequestedTime', 'casesForVentilatorsByRequestedTime', 'dollarsInFlight']
data_fields = ['region', 'periodType', 'timeToElapse',
               'reportedCases', 'totalHospitalBeds', 'population']
estimate_fields = ['data', 'impact', 'severeImpact']

'''
nameedTuples for esay access and to minimize keyError/s
'''
Region = namedtuple('Region', region_fields,
                    defaults=(None,) * len(region_fields))
Impact = namedtuple('Impact', impact_fields,
                    defaults=(None,) * len(impact_fields))
Data = namedtuple('Data', data_fields, defaults=(None,) * len(data_fields))
Estimate = namedtuple('Estimate', estimate_fields,
                      defaults=(Data(), Impact(), Impact()))

''' 
dict (improvised switch) of estimate calculations.
each returns new updated Impact namedTuple which is used to construct
and updates Estimate namedTuple
'''
impactCalcs = {
    'CI': lambda reportedCases, multiplier: Impact(
        reportedCases * multiplier),
    'IBRT': lambda impact, timeElapse: Impact(
        impact.currentlyInfected,
        impact.currentlyInfected * int(2**int(timeElapse / 3))),
    'SCBRT': lambda impact: Impact(
        impact.currentlyInfected,
        impact.infectionsByRequestedTime,
        int(impact.infectionsByRequestedTime * .15)),
    'HBBRT': lambda impact, hospitalBeds: Impact(
        impact.currentlyInfected,
        impact.infectionsByRequestedTime,
        impact.severeCasesByRequestedTime,
        int((hospitalBeds * .35) - impact.severeCasesByRequestedTime)),
    'CFICUBRT': lambda impact: Impact(
        impact.currentlyInfected,
        impact.infectionsByRequestedTime,
        impact.severeCasesByRequestedTime,
        impact.hospitalBedsByRequestedTime,
        int(impact.infectionsByRequestedTime * .05)),
    'CFVBRT': lambda impact: Impact(
        impact.currentlyInfected,
        impact.infectionsByRequestedTime,
        impact.severeCasesByRequestedTime,
        impact.hospitalBedsByRequestedTime,
        impact.casesForICUByRequestedTime,
        int(impact.infectionsByRequestedTime * .02)),
    'DIF': lambda impact, income, population, time: Impact(
        impact.currentlyInfected,
        impact.infectionsByRequestedTime,
        impact.severeCasesByRequestedTime,
        impact.hospitalBedsByRequestedTime,
        impact.casesForICUByRequestedTime,
        impact.casesForVentilatorsByRequestedTime,
        int((impact.infectionsByRequestedTime * income * population / time)))
}

# Normalizes period as days
duration_normaliser = {
    'days': lambda x: x,
    'weeks': lambda x: timedelta(weeks=x).days,
    'months': lambda x: 30 * x
}


def init(estimator):
    '''
    Initialize estimation by structure the data into a Data namedTuple
    '''
    @wraps(estimator)
    def wrapper(data):
        data = Data(
            Region(**data['region']),
            data['periodType'],
            data['timeToElapse'],
            data['reportedCases'],
            data['totalHospitalBeds'],
            data['population']
        )
        return estimator(data)
    return wrapper


def currentlyInfected(estimator):
    @wraps(estimator)
    def wrapper(data):
        # being the first estimate, defines the structure of the final output(Estimate)
        estimate = Estimate(
            data=data,
            impact=impactCalcs['CI'](data.reportedCases, 10),
            severeImpact=impactCalcs['CI'](data.reportedCases, 50))
        return estimator(estimate)

    return wrapper


def infectionsByRequestedTime(estimator):
    @wraps(estimator)
    def wrapper(estimate):
        time = duration_normaliser[estimate.data.periodType](
            estimate.data.timeToElapse)
        estimate = Estimate(
            data=estimate.data,
            impact=impactCalcs['IBRT'](estimate.impact, time),
            severeImpact=impactCalcs['IBRT'](estimate.severeImpact, time))
        return estimator(estimate)

    return wrapper


def severeCasesByRequestedTime(estimator):
    @wraps(estimator)
    def wrapper(estimate):
        estimate = Estimate(
            data=estimate.data,
            impact=impactCalcs['SCBRT'](estimate.impact),
            severeImpact=impactCalcs['SCBRT'](estimate.severeImpact))
        return estimator(estimate)
    return wrapper


def hospitalBedsByRequestedTime(estimator):
    @wraps(estimator)
    def wrapper(estimate):

        total_hospital_beds = estimate.data.totalHospitalBeds
        estimate = Estimate(
            data=estimate.data,
            impact=impactCalcs['HBBRT'](estimate.impact, total_hospital_beds),
            severeImpact=impactCalcs['HBBRT'](estimate.severeImpact, total_hospital_beds))
        return estimator(estimate)
    return wrapper


def casesForICUByRequestedTime(estimator):
    @wraps(estimator)
    def wrapper(estimate):
        estimate = Estimate(
            data=estimate.data,
            impact=impactCalcs['CFICUBRT'](estimate.impact),
            severeImpact=impactCalcs['CFICUBRT'](estimate.severeImpact))
        return estimator(estimate)
    return wrapper


def casesForVentilatorsByRequestedTime(estimator):
    @wraps(estimator)
    def wrapper(estimate):
        estimate = Estimate(
            data=estimate.data,
            impact=impactCalcs['CFVBRT'](estimate.impact),
            severeImpact=impactCalcs['CFVBRT'](estimate.severeImpact))
        return estimator(estimate)
    return wrapper


def dollarsInFlight(estimator):
    @wraps(estimator)
    def wrapper(estimate):
        time = duration_normaliser[estimate.data.periodType](
            estimate.data.timeToElapse)
        avg_daily_income = estimate.data.region.avgDailyIncomeInUSD
        avg_daily_income_population = estimate.data.region.avgDailyIncomePopulation

        estimate = Estimate(
            data=estimate.data,
            impact=impactCalcs['DIF'](
                estimate.impact, avg_daily_income, avg_daily_income_population, time),
            severeImpact=impactCalcs['DIF'](estimate.severeImpact, avg_daily_income, avg_daily_income_population, time))
        return estimator(estimate)
    return wrapper


def clean(estimator):
    '''
    restructure the final ouput from an Estimate namedTuple to dictionary
    '''
    @wraps(estimator)
    def wrapper(estimate):
        data = estimate._asdict()
        data.update({
            'data': estimate.data._asdict(),
            'impact': estimate.impact._asdict(),
            'severeImpact': estimate.severeImpact._asdict()
        })
        data['data']['region'] = estimate.data.region._asdict()
        return estimator(data)
    return wrapper


'''
builds estimatation as that data is sequentially transformed as it passes 
through each decorator
'''


@init
@currentlyInfected
@infectionsByRequestedTime
@severeCasesByRequestedTime
@hospitalBedsByRequestedTime
@casesForICUByRequestedTime
@casesForVentilatorsByRequestedTime
@dollarsInFlight
@clean
def estimator(data):
    return data
