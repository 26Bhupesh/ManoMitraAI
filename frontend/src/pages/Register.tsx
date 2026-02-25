import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { register } from "@/lib/api";
import { setAuthenticated } from "@/lib/session";
import type { Language } from "@/lib/types";

export default function Register() {
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);

  const [formData, setFormData] = useState({
    name: "",
    username: "",
    password: "",
    date_of_birth: "",
    preferred_language: "en" as Language,
    emergency_contact_name: "",
    emergency_contact_number: "",
    emergency_contact_relation: "",
  });

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleLanguageChange = (value: string) => {
    setFormData((prev) => ({
      ...prev,
      preferred_language: value as Language,
    }));
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Validation
      const requiredFields = [
        "name",
        "username",
        "password",
        "date_of_birth",
        "emergency_contact_name",
        "emergency_contact_number",
        "emergency_contact_relation",
      ];

      for (const field of requiredFields) {
        if (!formData[field as keyof typeof formData]) {
          toast({
            title: "Error",
            description: "Please fill in all required fields.",
            variant: "destructive",
          });
          setLoading(false);
          return;
        }
      }

      if (formData.password.length < 4) {
        toast({
          title: "Error",
          description: "Password must be at least 4 characters.",
          variant: "destructive",
        });
        setLoading(false);
        return;
      }

      const response = await register(formData);

      if (response.success && response.session_id && response.user_id) {
        const preferredLanguage = response.preferred_language || formData.preferred_language;
        
        setAuthenticated(
          response.session_id,
          response.user_id,
          response.username || formData.username,
          preferredLanguage
        );
        
        // Set UI language to user's preferred language
        i18n.changeLanguage(preferredLanguage);

        toast({
          title: "Success",
          description: "Registration successful!",
        });

        navigate("/");
      } else {
        toast({
          title: "Error",
          description: response.message || "Registration failed. Please try again.",
          variant: "destructive",
        });
      }
    } catch (error: any) {
      toast({
        title: "Error",
        description: error?.response?.data?.detail || "An error occurred during registration.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4 py-8">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader>
          <div className="text-center mb-4">
            <h1 className="text-3xl font-bold text-indigo-600">🧠 ManoMitraAI</h1>
          </div>
          <CardTitle className="text-center">Register</CardTitle>
          <CardDescription className="text-center">
            Create a new account
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleRegister} className="space-y-3">
            {/* Name */}
            <div className="space-y-1">
              <label className="text-sm font-medium">Full Name</label>
              <Input
                type="text"
                name="name"
                placeholder="Enter your name"
                value={formData.name}
                onChange={handleInputChange}
                disabled={loading}
              />
            </div>

            {/* Username */}
            <div className="space-y-1">
              <label className="text-sm font-medium">Username</label>
              <Input
                type="text"
                name="username"
                placeholder="Enter your username"
                value={formData.username}
                onChange={handleInputChange}
                disabled={loading}
              />
            </div>

            {/* Password */}
            <div className="space-y-1">
              <label className="text-sm font-medium">Password</label>
              <Input
                type="password"
                name="password"
                placeholder="Enter your password"
                value={formData.password}
                onChange={handleInputChange}
                disabled={loading}
              />
            </div>

            {/* Date of Birth */}
            <div className="space-y-1">
              <label className="text-sm font-medium">Date of Birth</label>
              <Input
                type="date"
                name="date_of_birth"
                value={formData.date_of_birth}
                onChange={handleInputChange}
                disabled={loading}
              />
            </div>

            {/* Preferred Language */}
            <div className="space-y-1">
              <label className="text-sm font-medium">Preferred Language</label>
              <Select value={formData.preferred_language} onValueChange={handleLanguageChange}>
                <SelectTrigger disabled={loading}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="en">English</SelectItem>
                  <SelectItem value="hi">Hindi</SelectItem>
                  <SelectItem value="mr">Marathi</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Emergency Contact Name */}
            <div className="space-y-1">
              <label className="text-sm font-medium">Emergency Contact Name</label>
              <Input
                type="text"
                name="emergency_contact_name"
                placeholder="Enter name"
                value={formData.emergency_contact_name}
                onChange={handleInputChange}
                disabled={loading}
              />
            </div>

            {/* Emergency Contact Number */}
            <div className="space-y-1">
              <label className="text-sm font-medium">Emergency Contact Number</label>
              <Input
                type="tel"
                name="emergency_contact_number"
                placeholder="Enter phone number"
                value={formData.emergency_contact_number}
                onChange={handleInputChange}
                disabled={loading}
              />
            </div>

            {/* Emergency Contact Relation */}
            <div className="space-y-1">
              <label className="text-sm font-medium">Relation</label>
              <Input
                type="text"
                name="emergency_contact_relation"
                placeholder="e.g., Parent, Sibling, Friend"
                value={formData.emergency_contact_relation}
                onChange={handleInputChange}
                disabled={loading}
              />
            </div>

            <Button
              type="submit"
              className="w-full bg-indigo-600 hover:bg-indigo-700"
              disabled={loading}
            >
              {loading ? "Loading..." : "Register"}
            </Button>
          </form>

          <div className="mt-4 text-center text-sm text-gray-600">
            Already have an account?
            <Link 
              to="/login" 
              className="text-indigo-600 hover:underline ml-1"
            >
              Login here
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
