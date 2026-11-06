#include <stdio.h>

int main(void) {
    int n;
    scanf("%d", &n);
    int result = n;
    for (int i = n - 1; i > 1; i--) {
        result *= i;
    }
    printf("%d\n", result);
    return 0;
}
