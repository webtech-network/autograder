import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        int n = new Scanner(System.in).nextInt();
        int result = n;
        for (int i = n - 1; i > 1; i--) {
            result *= i;
        }
        System.out.println(result);
    }
}
