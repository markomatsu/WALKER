#include <iostream>
using namespace std;

void logValue(int x) {
    if (x > 0) {
        cout << "positive";
    }
}

int main() {
    int x;
    cout << "Grade: ";
    cin >> x;

    if (x > 10 && x < 5) {
        cout << "never";
    }

    if (x >= 75) {
        cout << "passed";
    } else {
        cout << "failed";
    }

    return 0;
}
