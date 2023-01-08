import pandas as pd
import numpy as np
import statsmodels.api as sm
from scipy.special import expit
from scipy import optimize

def generateData(size=5000, verbose=False):
    """
    Generate a dataset corresponding to a DAG with the following structure:
    W1->W2, W1->A, W2->A, W2->Y, W2->R_Y, A->Y, A->R_A, Y->R_Y
    W1 and W2 are continuous variables.
    A and Y are binary variables.
    R_A and R_Y are missingness indicators for A and Y, respectively.

    return a 2-tuple: first is a pandas dataframe of the fully observed data,
    second is a pandas dataframe of the partially observed data
    """
    if verbose:
        print(size)

    W1 = np.random.normal(0, 1, size)

    W2 = np.random.normal(0, 1, size) + 1.4*W1
    
    A = np.random.binomial(1, expit(W1+W2), size)
    if verbose:
        print("proportion of A=1:", np.bincount(A)[1]/size)

    Y = np.random.binomial(1, expit(W2+A-0.4), size)
    if verbose:
        print("proportion of Y=1:", np.bincount(Y)[1]/size)

    # R_A=1 denotes observed value of A
    R_A = np.random.binomial(1, expit(2*A+0.3), size)
    if verbose:
        print("proportion of R_A=1:", np.bincount(R_A)[1]/size)

    # R_Y=1 denotes observed value of Y
    R_Y = np.random.binomial(1, expit(2*Y+W2+0.8), size)
    if verbose:
        print("proportion of R_Y=1:", np.bincount(R_Y)[1]/size)

    # create fully observed dataset
    full_data = pd.DataFrame({"A": A, "Y": Y, "W1": W1, "W2": W2, "R_A": R_A, "R_Y": R_Y})

    # create partially observed dataset
    A = full_data["A"].copy()
    A[full_data["R_A"] == 0] = -1
    Y = full_data["Y"].copy()
    Y[full_data["R_Y"] == 0] = -1
    partial_data = pd.DataFrame({"A": A, "Y": Y, "W1": W1, "W2": W2, "R_A": R_A, "R_Y": R_Y})

    return (full_data, partial_data)

def shadowIpwFunctional_Y(params, W_1, W_2, R_Y, Y, data):
    """
    Define the system of shadow IPW functions for a shadow variable W_1, a covariate W_2, missingness indicator
    R_Y, and self-censoring outcome variable Y.

    params is a list of four variables alpha_0, alpha_1, gamma_0, and gamma_1 in that order

    return values of the functionals based on the parameters
    """
    # p(R_Y=1 | Y=0)
    pRY_Y_0 = expit(params[0]+params[1]*data[W_2])
    pRY_1 = pRY_Y_0 / (pRY_Y_0 + ((params[2]+params[3]*data[W_2])**data[Y])*(1-pRY_Y_0))

    output1 = np.average( ((data[W_1]*data[W_2])*data[R_Y]) / pRY_1 - (data[W_1]*data[W_2]) )
    output2 = np.average( ((data[W_1]*data[W_2]+1)*data[R_Y]) / pRY_1 - (data[W_1]*data[W_2]+1) )
    output3 = np.average( ((data[W_1]*data[W_2]**2)*data[R_Y]) / pRY_1 - (data[W_1]*data[W_2]**2) )
    output4 = np.average( ((data[W_1]*data[W_2]**2+1)*data[R_Y]) / pRY_1 - (data[W_1]*data[W_2]**2+1) )

    return [output1, output2, output3, output4]

def rootsPrediction_Y(roots, W_2, Y, data):
    """
    Use the values of alpha and gamma contained in roots to make predictions on the value
    Y based on W2.
    """
    pRY_1_Y_0 = expit(roots[0] + roots[1]*data[W_2])
    predictions = pRY_1_Y_0 / (pRY_1_Y_0 + (roots[2]+roots[3]*data[W_2])**data[Y]*(1-pRY_1_Y_0))

    return predictions

def shadowIpwFunctional_A(params, W_1, R_A, A, data):
    """
    Define the system of shadow IPW functions for a shadow variable W_1, a missingness indicator
    R_A, and self-censoring outcome variable A.

    params is a list of four variables alpha_0, alpha_1, gamma_0, and gamma_1 in that order

    return values of the functionals based on the parameters
    """
    # p(R_Y=1 | Y=0)
    pRA_A_0 = expit(params[0])
    pRA_1 = pRA_A_0 / (pRA_A_0 + ((params[1])**data[A])*(1-pRA_A_0))

    output1 = np.average( ((data[W_1]*data[R_A])) / pRA_1 - (data[W_1]) )
    output2 = np.average( ((data[W_1]**2)*data[R_A]) / pRA_1 - (data[W_1]**2) )

    return [output1, output2]

def rootsPrediction_A(roots, A, data):
    """
    Use the values of alpha and gamma contained in roots to make predictions on the value
    A.
    """
    pRA_A_0 = expit(roots[0])
    predictions = pRA_A_0 / (pRA_A_0 + (roots[1])**data[A]*(1-pRA_A_0))

    return predictions

if __name__ == "__main__":
    np.random.seed(10)

    full_data, partial_data = generateData(verbose=True)

    roots_RA = optimize.root(shadowIpwFunctional_A, [0.0, 1.0], args=("W1", "R_A", "A", partial_data), method='hybr')
    print(roots_RA.x)

    # drop rows of data where A=1
    full_data_A_0 = full_data[full_data["A"] == 0]
    print(np.average(full_data_A_0["R_A"]))
    
    # drop rows of data where A=0
    full_data_A_1 = full_data[full_data["A"] == 1]
    print(np.average(full_data_A_1["R_A"]))

    # drop rows of data where R_A=0
    partial_data_A = partial_data[partial_data["R_A"] == 1]

    print(partial_data_A["A"])
    print(rootsPrediction_A(roots_RA.x, "A", partial_data_A))

    ##########################
    # caclulate propensity score of p(R_Y | A, W2)
    roots_RY = optimize.root(shadowIpwFunctional_Y, [0.0, 0.0, 1.0, 1.0], args=("W1", "W2", "R_Y", "Y", partial_data), method='hybr')
    print(roots_RY.x)

    model_R_Y = sm.GLM.from_formula(formula='R_Y ~ Y + W2', data=full_data, family=sm.families.Binomial()).fit()

    # drop rows of data where R_Y=0
    partial_data_Y = partial_data[partial_data["R_Y"] == 1]

    print(model_R_Y.predict(partial_data_Y))

    print(rootsPrediction_Y(roots_RY.x, "W2", "Y", partial_data_Y))
