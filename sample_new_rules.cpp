#include <iostream>
using namespace std;

int neverCalled(int unusedParam) {
    int localNeverUsed = 5;
    if (1) {
        return 42;
    }
    return 0;
}

int missingReturn(int x) {
    if (x > 0) {
        cout << "positive\n";
    }
}

class Account {
    int id;
    double funds;
    int shadow;

public:
    Account(int idValue) : id(idValue) {}

    void print() {
        cout << id << "\n";
    }
};

void loopTests() {
    int i = 0;
    while (i < 3);

    int j = 0;
    while (j < 3) {
        cout << j << "\n";
        break;
    }

    for (int k = 0; k < 2;) {
    }
}

void conditionalTests(int a) {
    if (a > 10 && a < 5) {
        cout << "never\n";
    }

    if (a > 0) {
        cout << "A\n";
    } else if (a > 0) {
        cout << "B\n";
    }

    if (a = 7) {
        cout << "assigned\n";
    }

    if (a == a) {
        cout << "same\n";
    }

    int z = 10 / 0;
    cout << z << "\n";
}

int main() {
    int input;
    cout << "Enter number: ";
    cin >> input;

    Account acct(1001);
    acct.print();

    switch (input) {
        case 1:
            cout << "one\n";
        case 2:
            cout << "two\n";
            break;
    }

    conditionalTests(input);
    loopTests();
    missingReturn(input);
    return 0;
}
