#include <iostream>
using namespace std;

int main() {
    int n = 11;
  
    int res = n & 1;

    if (res == 0)
        cout << "Even";

    else
        cout << "Odd";
    return 0;
}
