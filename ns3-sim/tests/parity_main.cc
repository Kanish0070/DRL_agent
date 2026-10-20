#include "../dqn-policy.h"
#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

int main(int argc, char* argv[])
{
    if (argc < 2)
    {
        std::cerr << "Usage: " << argv[0] << " <policy.txt> [obs.txt] [output_q.txt]\n"
                  << "       " << argv[0] << " --test-reject <bad_policy.txt>\n";
        return 2;
    }

    std::string arg1 = argv[1];
    if (arg1 == "--test-reject")
    {
        if (argc < 3)
        {
            std::cerr << "Error: --test-reject requires a policy file argument\n";
            return 2;
        }
        std::string bad_file = argv[2];
        try
        {
            DqnPolicy policy;
            policy.Load(bad_file);
            std::cerr << "FAIL: Corrupted policy was accepted without error!\n";
            return 1; // Failure: it should have rejected
        }
        catch (const std::exception& e)
        {
            std::cout << "SUCCESS: Rejected bad policy as expected: " << e.what() << "\n";
            return 0; // Success: exception thrown
        }
    }

    std::string policy_file = arg1;
    DqnPolicy policy;
    try
    {
        policy.Load(policy_file);
    }
    catch (const std::exception& e)
    {
        std::cerr << "Error loading policy: " << e.what() << "\n";
        return 1;
    }

    std::istream* input_stream = &std::cin;
    std::ifstream file_in;
    if (argc >= 3)
    {
        file_in.open(argv[2]);
        if (!file_in.is_open())
        {
            std::cerr << "Error opening input obs file: " << argv[2] << "\n";
            return 1;
        }
        input_stream = &file_in;
    }

    std::ostream* output_stream = &std::cout;
    std::ofstream file_out;
    if (argc >= 4)
    {
        file_out.open(argv[3]);
        if (!file_out.is_open())
        {
            std::cerr << "Error opening output Q file: " << argv[3] << "\n";
            return 1;
        }
        output_stream = &file_out;
    }

    std::string line;
    float obs[16];
    while (std::getline(*input_stream, line))
    {
        if (line.empty()) continue;
        std::istringstream iss(line);
        bool valid = true;
        for (int i = 0; i < 16; ++i)
        {
            if (!(iss >> obs[i]))
            {
                valid = false;
                break;
            }
        }
        if (!valid) continue;

        auto q = policy.Forward(obs);
        int act = policy.Act(obs);

        (*output_stream) << q[0] << " " << q[1] << " " << q[2] << " " << q[3]
                         << " " << act << "\n";
    }

    return 0;
}
