#include <iostream>

using namespace std;

int main() {
    
    char op;
    double num1;
    double num2;
    double result;
    
    cout << "******** CALCULATOR ********" << endl;
    
    cout << "Enter either (+, -, *, /): ";
    cin >> op;
    
    cout << "Enter first number: ";
    cin >> num1;
    
    cout << "Enter second number: ";
    cin >> num2;
    
    switch (op){
        case '+':
            result = num1 + num2;
            cout << "result: " << result << endl;
            break;
            
        case '-':
            result = num1 - num2;
            cout << "result: " << result << endl;
            break;
            
        case '*':
            result = num1 * num2;
            cout << "result: " << result << endl;
            break;
            
        case '/':
            result = num1 / num2;
            cout << "result: " << result << endl;
            break;
            
        default:
            cerr << "Invalid Response" << endl;
            break;
    }
            
    cout << "******************************" << endl;
    
    
    return 0;
}