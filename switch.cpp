#include <iostream>

using namespace std;

int main() {

    int x;

    cout << "Grade: ";
    cin >> x;

    switch (x) {
    case 76 ... 100:
        cout << "passed.";
        break;
    case 75:
        cout << "weak ahh.";
        break;
    default: 
        cout << "you can quit.";
        break;
}

    return 0;
}


