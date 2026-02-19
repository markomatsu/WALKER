#include<iostream>
using namespace std;

string validation(string inuser, string inpass){
    string user = "user1234";
    string pass = "1234";
     
    if (inpass == pass && inuser == user){
    string a = "Welcome!";
    return a;
    }
    else {
    string a = "Incorrect Username or Password";
    return a;
    }
}

string validationW(double amnt, double bal){
if (amnt < 0 || amnt > bal){
 string b = "Invalid Withdrawal Amount";
 return b;
 }
 
 else {
  string b = "Transaction Successful! Your new balance is: ";
  return b;
  }
}

double compW(double amnt, double bal){
double d;

d = bal - amnt;
return d;
}

double compD(double amnt, double bal){
double e;

e = bal + amnt;
return e;
}

string validationD(double amnt, double bal){
if (amnt < 0){
string c = "Invalid Deposit Amount";
return c;
 }
 else {
 string c = "Transaction Successful! Your new balance is: ";
 return c;
 }
}

int main()
{
    double bal = 10000.00;
    char t;
    string inuser;
    string inpass;
    
    cout << "Enter Username: ";
    cin >> inuser;
    cout << "Enter Password: ";
    cin >> inpass;
    
    string a = validation(inuser, inpass);
    
    cout << a;
    
    if (a == "Incorrect Username or Password"){
    return 0;
    }
    
    cout << " Enter Transaction Type (W for Withdrawal, D for Deposit): ";
    cin >> t;
    
    double amnt;
    string c = validationD(amnt, bal);
    string b = validationW(amnt, bal);
    
    switch(t){
    
    case 'W':
    cout << "Enter Amount to be Withdrawn: ";
    cin >> amnt;
    
    cout << b;
    
    if (b == "Invalid Withdrawal Amount"){
    return 0;
    }
    
    cout << compW(amnt, bal);
    break;
    
    case 'D':
    cout << "Enter Amount to be Deposited: ";
    cin >> amnt;
    
    cout << c;
    
    if (c == "Invalid Deposit Amount"){
    return 0;
    }
    
    cout << compD(amnt, bal);
    break;
    
    default:
    cout << "Invalid Transaction Type";
    
    }
    return 0;
}