#include <iostream>
using namespace std;

int main() {
    int x;
    cout << "Grade: ";
    cin >> x;

    if (x > 75) {
        cout << "passed.";
    } else if (x == 75) { // Use '==' for comparison, not '='
        cout << "weak ahh.";
    } else { // Handles x < 75
        cout << "you can quit.";
    }

    return 0;
}